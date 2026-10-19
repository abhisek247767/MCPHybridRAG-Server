

import ast
import operator




# Only these arithmetic operations are allowed.
BINARY_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}

UNARY_OPERATORS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}


def evaluate(node: ast.AST) -> int | float:
    """Evaluate a restricted arithmetic expression."""

    if isinstance(node, ast.Expression):
        return evaluate(node.body)

    if isinstance(node, ast.Constant):
        if type(node.value) not in (int, float):
            raise ValueError("Only numeric values are allowed.")
        return node.value

    if isinstance(node, ast.BinOp):
        operation = BINARY_OPERATORS.get(type(node.op))
        if operation is None:
            raise ValueError("Unsupported arithmetic operator.")

        left = evaluate(node.left)
        right = evaluate(node.right)

        # Prevent excessively large exponent calculations.
        if isinstance(node.op, ast.Pow):
            if abs(right) > 100 or abs(left) > 1_000_000:
                raise ValueError("Exponent is too large.")

        result = operation(left, right)

        if isinstance(result, complex):
            raise ValueError("Complex results are not supported.")

        if isinstance(result, float) and not (
            float("-inf") < result < float("inf")
        ):
            raise ValueError("Result is not finite.")

        if isinstance(result, int) and result.bit_length() > 4096:
            raise ValueError("Result is too large.")

        return result

    if isinstance(node, ast.UnaryOp):
        operation = UNARY_OPERATORS.get(type(node.op))
        if operation is None:
            raise ValueError("Unsupported unary operator.")
        return operation(evaluate(node.operand))

    raise ValueError("Invalid expression. Use basic arithmetic only.")









