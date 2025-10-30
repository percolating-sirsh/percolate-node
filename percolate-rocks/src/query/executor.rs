//! SQL query executor.
//!
//! Executes parsed SQL queries against entity storage.

use crate::types::{Result, DatabaseError, Entity};
use sqlparser::ast::{Statement, SelectItem, Expr, BinaryOperator, Value, Function, FunctionArg};

/// Execute SQL query against entities.
pub fn execute_query(statement: &Statement, entities: Vec<Entity>) -> Result<serde_json::Value> {
    if let Statement::Query(query) = statement {
        if let sqlparser::ast::SetExpr::Select(select) = query.body.as_ref() {
            // Filter by WHERE clause
            let mut filtered = if let Some(ref selection) = select.selection {
                entities.into_iter()
                    .filter(|entity| evaluate_where(selection, entity))
                    .collect()
            } else {
                entities
            };

            // Check for aggregates
            let has_agg = select.projection.iter().any(|item| {
                matches!(item, SelectItem::UnnamedExpr(Expr::Function(_)))
            });

            if has_agg {
                // Execute aggregate query
                return execute_aggregate(select, filtered);
            }

            // Apply ORDER BY
            if let Some(ref order_by) = query.order_by {
                apply_order_by(&mut filtered, order_by)?;
            }

            // Apply OFFSET (skip first N rows)
            if let Some(ref offset) = query.offset {
                if let sqlparser::ast::Offset { value: Expr::Value(Value::Number(n, _)), ..} = offset {
                    let offset_val: usize = n.parse().unwrap_or(0);
                    if offset_val < filtered.len() {
                        filtered = filtered.into_iter().skip(offset_val).collect();
                    } else {
                        // Offset beyond result set - return empty
                        filtered.clear();
                    }
                }
            }

            // Apply LIMIT
            if let Some(ref limit_expr) = query.limit {
                if let Expr::Value(Value::Number(n, _)) = limit_expr {
                    let limit: usize = n.parse().unwrap_or(usize::MAX);
                    filtered.truncate(limit);
                }
            }

            // Project fields
            let results = project_fields(select, filtered)?;

            return Ok(serde_json::json!(results));
        }
    }

    Err(DatabaseError::QueryError("Invalid query structure".to_string()))
}

/// Evaluate WHERE condition.
fn evaluate_where(expr: &Expr, entity: &Entity) -> bool {
    match expr {
        Expr::BinaryOp { left, op, right } => {
            evaluate_binary_op(left, op, right, entity)
        }
        Expr::Nested(inner) => evaluate_where(inner, entity),
        Expr::InList { expr: field_expr, list, negated } => {
            evaluate_in_list(field_expr, list, *negated, entity)
        }
        Expr::Like { expr: field_expr, pattern, negated, .. } => {
            evaluate_like(field_expr, pattern, *negated, entity)
        }
        _ => true,
    }
}

/// Evaluate binary operation.
fn evaluate_binary_op(left: &Expr, op: &BinaryOperator, right: &Expr, entity: &Entity) -> bool {
    // Handle AND/OR at top level
    match op {
        BinaryOperator::And => {
            return evaluate_where(left, entity) && evaluate_where(right, entity);
        }
        BinaryOperator::Or => {
            return evaluate_where(left, entity) || evaluate_where(right, entity);
        }
        _ => {}
    }

    // Get field name from left side
    let field_name = match left {
        Expr::Identifier(ident) => ident.value.as_str(),
        Expr::CompoundIdentifier(parts) => parts.last().unwrap().value.as_str(),
        _ => return true,
    };

    // Get field value from entity
    let field_value = match entity.properties.get(field_name) {
        Some(v) => v,
        None => return false,
    };

    // Get comparison value from right side
    let compare_value = match right {
        Expr::Value(val) => sql_value_to_json(val),
        _ => return true,
    };

    // Compare based on operator - now returns bool directly
    match op {
        BinaryOperator::Eq => values_equal(field_value, &compare_value),
        BinaryOperator::NotEq => !values_equal(field_value, &compare_value),
        BinaryOperator::Gt => values_greater_than(field_value, &compare_value),
        BinaryOperator::GtEq => values_greater_than(field_value, &compare_value) || values_equal(field_value, &compare_value),
        BinaryOperator::Lt => values_less_than(field_value, &compare_value),
        BinaryOperator::LtEq => values_less_than(field_value, &compare_value) || values_equal(field_value, &compare_value),
        _ => true,
    }
}

/// Check if values are equal with type coercion.
fn values_equal(left: &serde_json::Value, right: &serde_json::Value) -> bool {
    use serde_json::Value;

    match (left, right) {
        (Value::Number(a), Value::Number(b)) => {
            a.as_f64().unwrap_or(0.0) == b.as_f64().unwrap_or(0.0)
        }
        (Value::String(a), Value::String(b)) => a.eq_ignore_ascii_case(b),
        _ => left == right,
    }
}

/// Check if left > right.
fn values_greater_than(left: &serde_json::Value, right: &serde_json::Value) -> bool {
    use serde_json::Value;

    match (left, right) {
        (Value::Number(a), Value::Number(b)) => {
            a.as_f64().unwrap_or(0.0) > b.as_f64().unwrap_or(0.0)
        }
        (Value::String(a), Value::String(b)) => a > b,
        _ => false,
    }
}

/// Check if left < right.
fn values_less_than(left: &serde_json::Value, right: &serde_json::Value) -> bool {
    use serde_json::Value;

    match (left, right) {
        (Value::Number(a), Value::Number(b)) => {
            a.as_f64().unwrap_or(0.0) < b.as_f64().unwrap_or(0.0)
        }
        (Value::String(a), Value::String(b)) => a < b,
        _ => false,
    }
}

/// Convert SQL value to JSON.
fn sql_value_to_json(val: &Value) -> serde_json::Value {
    match val {
        Value::Number(n, _) => {
            if let Ok(i) = n.parse::<i64>() {
                serde_json::json!(i)
            } else if let Ok(f) = n.parse::<f64>() {
                serde_json::json!(f)
            } else {
                serde_json::Value::Null
            }
        }
        Value::SingleQuotedString(s) | Value::DoubleQuotedString(s) => serde_json::json!(s),
        Value::Boolean(b) => serde_json::json!(b),
        Value::Null => serde_json::Value::Null,
        _ => serde_json::Value::Null,
    }
}

/// Evaluate IN list expression.
fn evaluate_in_list(field_expr: &Expr, list: &[Expr], negated: bool, entity: &Entity) -> bool {
    // Get field name
    let field_name = match field_expr {
        Expr::Identifier(ident) => ident.value.as_str(),
        Expr::CompoundIdentifier(parts) => parts.last().unwrap().value.as_str(),
        _ => return !negated, // Can't evaluate, default to include
    };

    // Get field value
    let field_value = match entity.properties.get(field_name) {
        Some(v) => v,
        None => return negated, // Field not found - not in list (or in list if negated)
    };

    // Check if field value is in the list
    let in_list = list.iter().any(|expr| {
        if let Expr::Value(val) = expr {
            let compare_value = sql_value_to_json(val);
            values_equal(field_value, &compare_value)
        } else {
            false
        }
    });

    // Apply negation
    if negated {
        !in_list
    } else {
        in_list
    }
}

/// Evaluate LIKE pattern matching.
fn evaluate_like(field_expr: &Expr, pattern_expr: &Expr, negated: bool, entity: &Entity) -> bool {
    // Get field name
    let field_name = match field_expr {
        Expr::Identifier(ident) => ident.value.as_str(),
        Expr::CompoundIdentifier(parts) => parts.last().unwrap().value.as_str(),
        _ => return !negated,
    };

    // Get field value as string
    let field_value = match entity.properties.get(field_name) {
        Some(serde_json::Value::String(s)) => s.as_str(),
        _ => return negated, // Not a string or not found
    };

    // Get pattern string
    let pattern = match pattern_expr {
        Expr::Value(Value::SingleQuotedString(s)) | Expr::Value(Value::DoubleQuotedString(s)) => s.as_str(),
        _ => return !negated,
    };

    // Convert SQL LIKE pattern to regex
    // % = any characters, _ = single character
    let regex_pattern = pattern
        .replace("%", ".*")
        .replace("_", ".");
    let regex_pattern = format!("^{}$", regex_pattern);

    // Perform pattern match
    let matches = if let Ok(re) = regex::Regex::new(&regex_pattern) {
        re.is_match(field_value)
    } else {
        false
    };

    // Apply negation (NOT LIKE)
    if negated {
        !matches
    } else {
        matches
    }
}

/// Apply ORDER BY to entities.
fn apply_order_by(entities: &mut [Entity], order_by: &sqlparser::ast::OrderBy) -> Result<()> {
    if order_by.exprs.is_empty() {
        return Ok(());
    }

    let order = &order_by.exprs[0];
    let field_name = match &order.expr {
        Expr::Identifier(ident) => ident.value.clone(),
        _ => return Ok(()),
    };

    let ascending = order.asc.unwrap_or(true);

    entities.sort_by(|a, b| {
        let a_val = a.properties.get(&field_name);
        let b_val = b.properties.get(&field_name);

        let cmp = match (a_val, b_val) {
            (Some(av), Some(bv)) => compare_for_sort(av, bv),
            (Some(_), None) => std::cmp::Ordering::Greater,
            (None, Some(_)) => std::cmp::Ordering::Less,
            (None, None) => std::cmp::Ordering::Equal,
        };

        if ascending { cmp } else { cmp.reverse() }
    });

    Ok(())
}

/// Compare values for sorting.
fn compare_for_sort(a: &serde_json::Value, b: &serde_json::Value) -> std::cmp::Ordering {
    use serde_json::Value;

    match (a, b) {
        (Value::Number(an), Value::Number(bn)) => {
            let af = an.as_f64().unwrap_or(0.0);
            let bf = bn.as_f64().unwrap_or(0.0);
            af.partial_cmp(&bf).unwrap_or(std::cmp::Ordering::Equal)
        }
        (Value::String(as_), Value::String(bs)) => as_.cmp(bs),
        (Value::Bool(ab), Value::Bool(bb)) => ab.cmp(bb),
        _ => std::cmp::Ordering::Equal,
    }
}

/// Project fields from entities.
fn project_fields(select: &sqlparser::ast::Select, entities: Vec<Entity>) -> Result<Vec<serde_json::Value>> {
    let mut results = Vec::new();

    for entity in entities {
        let mut row = serde_json::Map::new();

        for item in &select.projection {
            match item {
                SelectItem::Wildcard(_) => {
                    if let Some(obj) = entity.properties.as_object() {
                        for (k, v) in obj {
                            row.insert(k.clone(), v.clone());
                        }
                    }
                }
                SelectItem::UnnamedExpr(Expr::Identifier(ident)) => {
                    let field_name = &ident.value;
                    if let Some(val) = entity.properties.get(field_name) {
                        row.insert(field_name.clone(), val.clone());
                    }
                }
                _ => {}
            }
        }

        results.push(serde_json::Value::Object(row));
    }

    Ok(results)
}

/// Execute aggregate query.
fn execute_aggregate(select: &sqlparser::ast::Select, entities: Vec<Entity>) -> Result<serde_json::Value> {
    let mut result = serde_json::Map::new();

    for item in &select.projection {
        if let SelectItem::UnnamedExpr(Expr::Function(func)) = item {
            let (name, value) = evaluate_aggregate(func, &entities)?;
            result.insert(name, value);
        }
    }

    Ok(serde_json::json!([serde_json::Value::Object(result)]))
}

/// Evaluate aggregate function.
fn evaluate_aggregate(func: &Function, entities: &[Entity]) -> Result<(String, serde_json::Value)> {
    let func_name = func.name.to_string().to_uppercase();

    match func_name.as_str() {
        "COUNT" => {
            let count = entities.len();
            Ok((func_name.to_lowercase(), serde_json::json!(count)))
        }
        "SUM" | "AVG" | "MIN" | "MAX" => {
            let field_name = extract_field_from_func_args(&func.args)?;

            let values: Vec<f64> = entities
                .iter()
                .filter_map(|e| e.properties.get(&field_name))
                .filter_map(|v| v.as_f64().or_else(|| v.as_i64().map(|i| i as f64)))
                .collect();

            let result = match func_name.as_str() {
                "SUM" => values.iter().sum(),
                "AVG" => if values.is_empty() { 0.0 } else { values.iter().sum::<f64>() / values.len() as f64 },
                "MIN" => values.iter().copied().fold(f64::INFINITY, f64::min),
                "MAX" => values.iter().copied().fold(f64::NEG_INFINITY, f64::max),
                _ => 0.0,
            };

            Ok((func_name.to_lowercase(), serde_json::json!(result)))
        }
        _ => Err(DatabaseError::QueryError(format!("Unsupported aggregate function: {}", func_name))),
    }
}

/// Extract field name from function arguments.
fn extract_field_from_func_args(args: &sqlparser::ast::FunctionArguments) -> Result<String> {
    use sqlparser::ast::{FunctionArguments, FunctionArgumentList, FunctionArgExpr};

    match args {
        FunctionArguments::List(FunctionArgumentList { args, .. }) => {
            if args.is_empty() {
                return Err(DatabaseError::QueryError("Missing function argument".to_string()));
            }

            match &args[0] {
                FunctionArg::Unnamed(arg_expr) => {
                    match arg_expr {
                        // Handle COUNT(*)
                        FunctionArgExpr::Wildcard => {
                            return Ok("*".to_string());
                        }
                        // Handle COUNT(field)
                        FunctionArgExpr::Expr(Expr::Identifier(ident)) => {
                            return Ok(ident.value.clone());
                        }
                        _ => {}
                    }
                }
                FunctionArg::Named { arg, .. } => {
                    if let FunctionArgExpr::Expr(Expr::Identifier(ident)) = arg {
                        return Ok(ident.value.clone());
                    }
                }
            }

            Err(DatabaseError::QueryError("Invalid function argument".to_string()))
        }
        _ => Err(DatabaseError::QueryError("Unsupported function argument format".to_string())),
    }
}
