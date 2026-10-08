from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.bin import Bin
from app.schemas.collection import CollectionCreate, CollectionRecord
from app.schemas.priority import CollectionPlan, PriorityResult
from app.services import bin_service, collection_service
from app.services.collection_plan import build_collection_plan
from app.services.priority_engine import rank_bins

router = APIRouter(prefix="/api/v1")


@router.get("/bins", response_model=list[Bin])
def list_bins(db: Session = Depends(get_db)):
    return bin_service.list_bins(db)


@router.get("/bins/{bin_id}", response_model=Bin)
def get_bin(bin_id: str, db: Session = Depends(get_db)):
    bin_ = bin_service.get_bin(db, bin_id)
    if bin_ is None:
        raise HTTPException(status_code=404, detail=f"Bin {bin_id} not found")
    return bin_


@router.get("/priorities", response_model=list[PriorityResult])
def list_priorities(db: Session = Depends(get_db)):
    return [p for _, p in rank_bins(bin_service.list_bins(db))]


@router.get("/collection-plan", response_model=CollectionPlan)
def collection_plan(db: Session = Depends(get_db)):
    return build_collection_plan(bin_service.list_bins(db))


@router.get("/collections", response_model=list[CollectionRecord])
def list_collections(bin_id: str | None = None, limit: int = Query(50, ge=1, le=200), db: Session = Depends(get_db)):
    return collection_service.list_records(db, bin_id=bin_id, limit=limit)


@router.post("/collections", response_model=CollectionRecord, status_code=201)
def create_collection(payload: CollectionCreate, db: Session = Depends(get_db)):
    try:
        return collection_service.create_record(db, payload)
    except collection_service.BinNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
