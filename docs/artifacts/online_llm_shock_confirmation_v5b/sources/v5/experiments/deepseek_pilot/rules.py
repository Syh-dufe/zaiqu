"""Interpret bounded rule expressions without executing generated Python code."""
import ast
import math
import operator

FEATURES = {"agent", "inventory", "backlog", "pipeline", "arrival", "incoming",
            "recent", "baseline", "growth", "happo"}
BINARY = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
          ast.Div: operator.truediv}
COMPARE = {ast.Gt: operator.gt, ast.GtE: operator.ge, ast.Lt: operator.lt,
           ast.LtE: operator.le, ast.Eq: operator.eq, ast.NotEq: operator.ne}
FUNCTIONS = {"min": min, "max": max, "abs": abs}


def parse_expression(text):
    if not isinstance(text, str) or len(text) > 300:
        raise ValueError("expression must be a string of at most 300 characters")
    tree = ast.parse(text, mode="eval").body
    if len(list(ast.walk(tree))) > 120:
        raise ValueError("expression is too large")

    def check(node, depth=0):
        if depth > 20:
            raise ValueError("expression is too deep")
        if isinstance(node, ast.Constant):
            if type(node.value) not in (int, float, bool) or not math.isfinite(node.value) or abs(node.value) > 1000:
                raise ValueError("invalid numeric constant")
        elif isinstance(node, ast.Name):
            if node.id not in FEATURES:
                raise ValueError("unknown feature")
        elif isinstance(node, ast.BinOp) and type(node.op) in BINARY:
            check(node.left, depth+1); check(node.right, depth+1)
        elif isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub, ast.Not)):
            check(node.operand, depth+1)
        elif isinstance(node, ast.BoolOp) and isinstance(node.op, (ast.And, ast.Or)):
            for child in node.values: check(child, depth+1)
        elif isinstance(node, ast.Compare) and all(type(op) in COMPARE for op in node.ops):
            check(node.left, depth+1)
            for child in node.comparators: check(child, depth+1)
        elif isinstance(node, ast.IfExp):
            for child in (node.test, node.body, node.orelse): check(child, depth+1)
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in FUNCTIONS and not node.keywords:
            if not (len(node.args) == 1 if node.func.id == "abs" else 2 <= len(node.args) <= 6):
                raise ValueError("invalid function argument count")
            for child in node.args: check(child, depth+1)
        else:
            raise ValueError("unsupported expression construct")
    check(tree)
    return tree


def evaluate(node, features):
    if isinstance(node, ast.Constant): return node.value
    if isinstance(node, ast.Name): return features[node.id]
    if isinstance(node, ast.BinOp): return BINARY[type(node.op)](evaluate(node.left, features), evaluate(node.right, features))
    if isinstance(node, ast.UnaryOp):
        value = evaluate(node.operand, features)
        return not value if isinstance(node.op, ast.Not) else (-value if isinstance(node.op, ast.USub) else value)
    if isinstance(node, ast.BoolOp):
        if isinstance(node.op, ast.And): return all(evaluate(v, features) for v in node.values)
        return any(evaluate(v, features) for v in node.values)
    if isinstance(node, ast.Compare):
        previous = evaluate(node.left, features)
        for op, child in zip(node.ops, node.comparators):
            current = evaluate(child, features)
            if not COMPARE[type(op)](previous, current): return False
            previous = current
        return True
    if isinstance(node, ast.IfExp): return evaluate(node.body if evaluate(node.test,features) else node.orelse,features)
    if isinstance(node, ast.Call): return FUNCTIONS[node.func.id](*[evaluate(v,features) for v in node.args])
    raise ValueError("invalid expression")


def compile_rule(data):
    if not isinstance(data, dict) or not isinstance(data.get("rules"),list) or not 1 <= len(data["rules"]) <= 4:
        raise ValueError("expected one to four rules")
    result = []
    for entry in data["rules"]:
        if not isinstance(entry,dict) or set(entry) != {"when","delta"}:
            raise ValueError("rule must contain when and delta only")
        result.append((parse_expression(entry["when"]),parse_expression(entry["delta"])))
    return result


def rule_delta(compiled, features):
    for condition, expression in compiled:
        if evaluate(condition, features):
            return float(evaluate(expression, features))
    return 0.0


def manual_delta(f):
    if f["recent"] > 1.3*f["baseline"] or f["backlog"] > 5:
        return math.ceil(min(6,max(0,(4*max(f["incoming"],f["recent"])+f["backlog"]-f["inventory"]-f["pipeline"])/4)))
    return 0


def bounded_order(base, delta):
    if not math.isfinite(delta): raise ValueError("non-finite correction")
    return min(20,max(0,int(base)+int(round(min(6,max(-6,delta))))))
