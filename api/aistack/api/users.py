# -*- coding: utf-8 -*-
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse

from aistack.schemas.users import User, UserCreate, UserUpdate, UserPublic, UsersPublic
from aistack.server.deps import ListParamsDep, SessionDep

router = APIRouter()

@router.get("", response_model=UsersPublic)
async def get_users(session: SessionDep, params: ListParamsDep, search: str = None):
    fuzzy_fields = {}
    if search:
        fuzzy_fields = {"username": search, "full_name": search}

    return await User.paginated_by_query(
        session=session,
        fuzzy_fields=fuzzy_fields,
        page=params.page,
        per_page=params.perPage,
    )