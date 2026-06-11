"""CSV/File upload endpoint — parse menu data from CSV."""

import csv
import io
import logging

from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter()


class CsvParseResult(BaseModel):
    categories: list[dict]
    dishes: list[dict]
    errors: list[str]
    total_rows: int


@router.post("/csv")
async def upload_csv(file: UploadFile = File(...)) -> CsvParseResult:
    """Parse a CSV file containing menu data and return structured dishes/categories."""
    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(400, "只支持 .csv 文件")

    content = await file.read()
    text = content.decode("utf-8-sig")  # handle BOM

    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise HTTPException(400, "CSV 文件为空或格式不正确")

    # Normalize column names
    col_map = {}
    for col in reader.fieldnames:
        c = col.strip().lower().replace(" ", "_")
        if c in ("name", "菜品名", "菜品名称", "商品名", "商品名称"):
            col_map[col] = "name"
        elif c in ("category", "分类", "类别", "品类", "category_name"):
            col_map[col] = "category"
        elif c in ("price", "价格", "单价", "售价"):
            col_map[col] = "price"
        elif c in ("description", "描述", "简介", "说明"):
            col_map[col] = "description"
        elif c in ("image_url", "image", "图片", "图片链接", "图片url"):
            col_map[col] = "image_url"
        elif c in ("tags", "标签", "标记"):
            col_map[col] = "tags"
        else:
            col_map[col] = c

    if "name" not in col_map.values():
        raise HTTPException(400, "CSV 缺少「菜品名」列")

    categories: dict[str, dict] = {}
    dishes: list[dict] = []
    errors: list[str] = []
    row_num = 0

    for row in reader:
        row_num += 1
        try:
            # Map columns
            mapped = {}
            for orig_col, standard_col in col_map.items():
                mapped[standard_col] = row[orig_col].strip() if row.get(orig_col) else ""

            name = mapped.get("name", "")
            if not name:
                errors.append(f"第 {row_num} 行缺少菜品名，已跳过")
                continue

            category = mapped.get("category", "未分类")
            price_str = mapped.get("price", "0").replace("¥", "").replace("￥", "").strip()
            try:
                price = float(price_str) if price_str else 0
            except ValueError:
                errors.append(f"第 {row_num} 行价格「{price_str}」格式错误，使用 0")
                price = 0

            # Collect category
            if category not in categories:
                categories[category] = {"name": category, "dish_count": 0}
            categories[category]["dish_count"] += 1

            dish = {
                "name": name,
                "category_name": category,
                "price": price,
                "description": mapped.get("description", ""),
                "image_url": mapped.get("image_url", ""),
                "tags": [t.strip() for t in mapped.get("tags", "").split("、") if t.strip()] if mapped.get("tags") else [],
            }
            dishes.append(dish)
        except Exception as e:
            errors.append(f"第 {row_num} 行解析失败：{e}")

    return CsvParseResult(
        categories=list(categories.values()),
        dishes=dishes,
        errors=errors,
        total_rows=row_num,
    )
