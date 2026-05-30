from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.api.schemas import (
    AttackRequest,
    AttackCityRequest,
    BuildImprovementRequest,
    BuildRequest,
    CancelBuildRequest,
    PurchaseStructureRequest,
    FoundCityRequest,
    GameStateOut,
    MessageRequest,
    MoveRequest,
    ResearchRequest,
    state_to_out,
)
from app.api.store import store
from app.engine.diplomacy import DiplomacyError, MessageKind, SendMessage, apply_diplomatic_action
from app.engine.directives import (
    CancelProduction,
    DirectiveError,
    PurchaseStructure,
    QueueProduction,
    apply_directive,
)
from app.engine.city_founding import FoundError, found_city
from app.engine.combat import CombatError, attack, attack_city
from app.engine.hex import Hex
from app.engine.improvements import ImprovementError, start_improvement
from app.engine.models import BuildItem, BuildKind, BuildingType, UnitType
from app.engine.movement import MoveError, move_unit
from app.engine.research import ResearchError, set_research
from app.engine.terrain import Improvement

router = APIRouter(prefix="/games/{game_id}/actions", tags=["actions"])


def _load(game_id: int):  # type: ignore[no-untyped-def]
    try:
        return store.get(game_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="game not found")


@router.post("/move", response_model=GameStateOut)
def action_move(game_id: int, req: MoveRequest) -> GameStateOut:
    state = _load(game_id)
    try:
        new_state = move_unit(state, req.unit_id, Hex(req.q, req.r))
    except MoveError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    store.put(game_id, new_state)
    return state_to_out(game_id, new_state)


@router.post("/attack", response_model=GameStateOut)
def action_attack(game_id: int, req: AttackRequest) -> GameStateOut:
    state = _load(game_id)
    try:
        new_state = attack(state, req.attacker_id, req.defender_id)
    except CombatError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    store.put(game_id, new_state)
    return state_to_out(game_id, new_state)


@router.post("/attack-city", response_model=GameStateOut)
def action_attack_city(game_id: int, req: AttackCityRequest) -> GameStateOut:
    state = _load(game_id)
    try:
        new_state = attack_city(state, req.attacker_id, req.city_id)
    except CombatError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    store.put(game_id, new_state)
    return state_to_out(game_id, new_state)


@router.post("/found", response_model=GameStateOut)
def action_found(game_id: int, req: FoundCityRequest) -> GameStateOut:
    state = _load(game_id)
    try:
        new_state = found_city(state, req.unit_id, req.name)
    except FoundError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    store.put(game_id, new_state)
    return state_to_out(game_id, new_state)


@router.post("/research", response_model=GameStateOut)
def action_research(game_id: int, req: ResearchRequest) -> GameStateOut:
    state = _load(game_id)
    try:
        new_state = set_research(state, req.civ_id, req.tech_id)
    except ResearchError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    store.put(game_id, new_state)
    return state_to_out(game_id, new_state)


@router.post("/build", response_model=GameStateOut)
def action_build(game_id: int, req: BuildRequest) -> GameStateOut:
    state = _load(game_id)
    try:
        if req.item_id is not None:
            item_id = req.item_id
        elif req.unit_type is not None:
            item_id = req.unit_type
        else:
            raise ValueError("missing item_id")
        build_kind = BuildKind(req.build_kind)
        if build_kind is BuildKind.UNIT:
            item = BuildItem.unit(UnitType(item_id))
        else:
            item = BuildItem.building(BuildingType(item_id))
        new_state = apply_directive(
            state,
            req.civ_id,
            QueueProduction(city_id=req.city_id, item=item),
        )
    except (DirectiveError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    store.put(game_id, new_state)
    return state_to_out(game_id, new_state)


@router.post("/cancel-build", response_model=GameStateOut)
def action_cancel_build(game_id: int, req: CancelBuildRequest) -> GameStateOut:
    state = _load(game_id)
    try:
        new_state = apply_directive(
            state,
            req.civ_id,
            CancelProduction(city_id=req.city_id, index=req.index),
        )
    except (DirectiveError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    store.put(game_id, new_state)
    return state_to_out(game_id, new_state)


@router.post("/purchase-structure", response_model=GameStateOut)
def action_purchase_structure(
    game_id: int, req: PurchaseStructureRequest
) -> GameStateOut:
    state = _load(game_id)
    try:
        new_state = apply_directive(
            state,
            req.civ_id,
            PurchaseStructure(city_id=req.city_id, category=req.category),
        )
    except (DirectiveError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    store.put(game_id, new_state)
    return state_to_out(game_id, new_state)


@router.post("/improve", response_model=GameStateOut)
def action_improve(game_id: int, req: BuildImprovementRequest) -> GameStateOut:
    state = _load(game_id)
    try:
        improvement = Improvement(req.improvement)
        new_state = start_improvement(state, req.unit_id, improvement)
    except (ImprovementError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    store.put(game_id, new_state)
    return state_to_out(game_id, new_state)


@router.post("/message", response_model=GameStateOut)
def action_message(game_id: int, req: MessageRequest) -> GameStateOut:
    state = _load(game_id)
    try:
        kind = MessageKind(req.kind)
        new_state = apply_diplomatic_action(
            state,
            req.from_civ_id,
            SendMessage(to_civ_id=req.to_civ_id, kind=kind, text=req.text),
        )
    except (DiplomacyError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    store.put(game_id, new_state)
    return state_to_out(game_id, new_state)
