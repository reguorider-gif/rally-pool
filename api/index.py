"""
Vercel serverless 入口 — 将 app.py 的 FastAPI 实例导出为 ASGI app。
"""
import sys
from pathlib import Path

# 确保项目根目录在 sys.path 中，以便 server.py 可被导入
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app import app