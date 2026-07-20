"""计算工具：安全四则运算、面积换算"""
import ast
import operator
from typing import Dict, Any
from backend.agents.tools.base_tool import BaseTool, ToolResult

_SAFE_OPS = {
    ast.Add: operator.add, ast.Sub: operator.sub,
    ast.Mult: operator.mul, ast.Div: operator.truediv,
    ast.Pow: operator.pow, ast.USub: operator.neg,
    ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod,
}

class CalcTool(BaseTool):
    """安全计算器：面积换算、四则运算"""

    name = "calculator"
    description = "执行数学计算，如面积换算（50平方英尺=？平方米）、加减乘除"
    parameters = {
        "expression": {
            "type": "string",
            "description": "数学表达式，如 50*0.0929 或 (3+5)*2",
            "required": True,
        }
    }

    async def execute(self, expression: str = "", **kw) -> ToolResult:
        try:
            tree = ast.parse(expression.strip(), mode="eval")
            result = self._eval(tree.body)
            return ToolResult(success=True, data={
                "answer": f"{expression} = {result}",
                "result": result,
            })
        except Exception as e:
            return ToolResult(success=False, error=f"计算失败: {e}")

    @staticmethod
    def _eval(node):
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
            return -CalcTool._eval(node.operand)
        if isinstance(node, ast.BinOp):
            op = _SAFE_OPS.get(type(node.op))
            if not op:
                raise ValueError(f"不支持的操作: {type(node.op).__name__}")
            return op(CalcTool._eval(node.left), CalcTool._eval(node.right))
        raise ValueError(f"不支持的表达式: {type(node).__name__}")