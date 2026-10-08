from fastapi import APIRouter, HTTPException

from app.schemas.bin import Bin
from app.schemas.priority import CollectionPlan, PriorityResult
from app.services import bin_service
from app.services.collection_plan import build_collection_plan
from app.services.priority_engine import rank_bins

router = APIRouter(prefix="/api/v1")


@router.get("/bins", response_model=list[Bin])
def list_bins():
    return bin_service.list_bins()


@router.get("/bins/{bin_id}", response_model=Bin)
def get_bin(bin_id: str):
    bin_ = bin_service.get_bin(bin_id)
    if bin_ is None:
        raise HTTPException(status_code=404, detail=f"Bin {bin_id} not found")
    return bin_


@router.get("/priorities", response_model=list[PriorityResult])
def list_priorities():
    return [p for _, p in rank_bins(bin_service.list_bins())]


@router.get("/collection-plan", response_model=CollectionPlan)
def collection_plan():
    return build_collection_plan(bin_service.list_bins())
