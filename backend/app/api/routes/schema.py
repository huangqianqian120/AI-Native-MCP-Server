from fastapi import APIRouter, HTTPException

from app.api.models.requests import InferSchemaRequest
from app.api.models.business_schema import BusinessSchema
from app.core.schema_inferrer import SchemaInferrer

router = APIRouter()
inferrer = SchemaInferrer()


@router.post("/infer")
async def infer_schema(req: InferSchemaRequest) -> BusinessSchema:
    """Analyze user input via LLM and return a complete BusinessSchema."""
    try:
        schema = await inferrer.infer(req)
        return schema
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Schema inference failed: {e}")
