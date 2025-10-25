# -*- coding: utf-8 -*-
from typing import Annotated, Optional
from fastapi import Depends
from sqlmodel.ext.asyncio.session import AsyncSession
from aistack.schemas.users import User
from aistack.server.auth import get_admin_user, get_current_user, get_optional_user
from aistack.server.db import get_session
from aistack.schemas.common import ListParams

SessionDep = Annotated[AsyncSession, Depends(get_session)]
ListParamsDep = Annotated[ListParams, Depends(ListParams)]
CurrentUserDep = Annotated[User, Depends(get_current_user)]
CurrentAdminUserDep = Annotated[User, Depends(get_admin_user)]
OptionalUserDep = Annotated[Optional[User], Depends(get_optional_user)]

