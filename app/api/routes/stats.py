from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlmodel import Session, select

from app.api.routes.auth import CurrentUserDep
from app.db.session import get_session
from app.models.statistics import MealEntry, StatisticsDay
from app.schemas.statistics import (
    DishNamesRead,
    MealCreate,
    MealIngredient,
    MealRead,
    MealTotalMacros,
    MealsByDishRead,
    StatisticsDayRead,
    StatisticsRead,
)

router = APIRouter(prefix="/stats", tags=["stats"])

SessionDep = Annotated[Session, Depends(get_session)]


def _require_user_id(current_user: CurrentUserDep) -> int:
    user_id = current_user.id
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="User record is invalid",
        )
    return user_id


def _to_utc_naive(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def _serialize_meal(meal: MealEntry) -> MealRead:
    if meal.id is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Meal record is invalid",
        )
    return MealRead(
        id=meal.id,
        time=meal.time,
        dish_name=meal.dish_name,
        total_weight=meal.total_weight,
        total_macros=MealTotalMacros.model_validate(meal.total_macros),
        ingredients=[MealIngredient.model_validate(item) for item in meal.ingredients],
    )


@router.post("/meals", response_model=MealRead, status_code=status.HTTP_201_CREATED)
def create_meal(
    payload: MealCreate,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> MealRead:
    user_id = _require_user_id(current_user)
    dish_name = payload.dish_name.strip()
    if not dish_name:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="dishName must not be empty",
        )

    meal_time = _to_utc_naive(payload.time)
    day_value = meal_time.date()

    statement = select(StatisticsDay).where(
        StatisticsDay.user_id == user_id,
        StatisticsDay.day == day_value,
    )
    statistics_day = session.exec(statement).first()
    if statistics_day is None:
        statistics_day = StatisticsDay(user_id=user_id, day=day_value)
        session.add(statistics_day)
        session.flush()

    if statistics_day.id is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Statistics day creation failed",
        )

    meal = MealEntry(
        statistics_day_id=statistics_day.id,
        user_id=user_id,
        time=meal_time,
        dish_name=dish_name,
        total_weight=payload.total_weight,
        total_macros=payload.total_macros.model_dump(by_alias=True, exclude_none=True),
        ingredients=[item.model_dump(by_alias=True, exclude_none=True) for item in payload.ingredients],
    )
    session.add(meal)
    session.commit()
    session.refresh(meal)

    return _serialize_meal(meal)


@router.get("", response_model=StatisticsRead)
def get_statistics(
    session: SessionDep,
    current_user: CurrentUserDep,
) -> StatisticsRead:
    user_id = _require_user_id(current_user)

    days_statement = (
        select(StatisticsDay)
        .where(StatisticsDay.user_id == user_id)
        .order_by(StatisticsDay.day.desc())
    )
    statistics_days = session.exec(days_statement).all()
    if not statistics_days:
        return StatisticsRead(days=[])

    meals_statement = (
        select(MealEntry)
        .where(MealEntry.user_id == user_id)
        .order_by(MealEntry.time.desc(), MealEntry.id.desc())
    )
    meals = session.exec(meals_statement).all()

    meals_by_day_id: dict[int, list[MealRead]] = defaultdict(list)
    for meal in meals:
        meals_by_day_id[meal.statistics_day_id].append(_serialize_meal(meal))

    days = [
        StatisticsDayRead(day=day.day, meals=meals_by_day_id.get(day.id or 0, []))
        for day in statistics_days
    ]
    return StatisticsRead(days=days)


@router.get("/days/{day}/meals", response_model=StatisticsDayRead)
def get_daily_meals(
    day: date,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> StatisticsDayRead:
    user_id = _require_user_id(current_user)
    day_statement = select(StatisticsDay).where(
        StatisticsDay.user_id == user_id,
        StatisticsDay.day == day,
    )
    statistics_day = session.exec(day_statement).first()
    if statistics_day is None:
        return StatisticsDayRead(day=day, meals=[])

    meals_statement = (
        select(MealEntry)
        .where(
            MealEntry.user_id == user_id,
            MealEntry.statistics_day_id == statistics_day.id,
        )
        .order_by(MealEntry.time.desc(), MealEntry.id.desc())
    )
    meals = session.exec(meals_statement).all()

    return StatisticsDayRead(
        day=statistics_day.day,
        meals=[_serialize_meal(meal) for meal in meals],
    )


@router.delete("/days/{day}", status_code=status.HTTP_204_NO_CONTENT)
def delete_day(
    day: date,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> None:
    user_id = _require_user_id(current_user)
    day_statement = select(StatisticsDay).where(
        StatisticsDay.user_id == user_id,
        StatisticsDay.day == day,
    )
    statistics_day = session.exec(day_statement).first()
    if statistics_day is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Statistics day not found",
        )

    meals_statement = select(MealEntry).where(MealEntry.statistics_day_id == statistics_day.id)
    meals = session.exec(meals_statement).all()
    for meal in meals:
        session.delete(meal)
    session.delete(statistics_day)
    session.commit()


@router.delete("/days/{day}/meals/{meal_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_daily_meal(
    day: date,
    meal_id: int,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> None:
    user_id = _require_user_id(current_user)
    day_statement = select(StatisticsDay).where(
        StatisticsDay.user_id == user_id,
        StatisticsDay.day == day,
    )
    statistics_day = session.exec(day_statement).first()
    if statistics_day is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Statistics day not found",
        )

    meal_statement = select(MealEntry).where(
        MealEntry.id == meal_id,
        MealEntry.user_id == user_id,
        MealEntry.statistics_day_id == statistics_day.id,
    )
    meal = session.exec(meal_statement).first()
    if meal is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Meal not found in this day",
        )

    session.delete(meal)
    remaining_statement = select(MealEntry).where(
        MealEntry.user_id == user_id,
        MealEntry.statistics_day_id == statistics_day.id,
        MealEntry.id != meal_id,
    )
    has_remaining = session.exec(remaining_statement).first() is not None
    if not has_remaining:
        session.delete(statistics_day)
    session.commit()


@router.get("/dish-names", response_model=DishNamesRead)
def get_dish_names(
    session: SessionDep,
    current_user: CurrentUserDep,
) -> DishNamesRead:
    user_id = _require_user_id(current_user)
    statement = (
        select(MealEntry.dish_name)
        .where(MealEntry.user_id == user_id)
        .distinct()
        .order_by(func.lower(MealEntry.dish_name))
    )
    dish_names = session.exec(statement).all()
    return DishNamesRead(dish_names=[name for name in dish_names if isinstance(name, str)])


@router.get("/dishes", response_model=MealsByDishRead)
def get_meals_by_dish_name(
    dish_name: Annotated[str, Query(alias="dishName", min_length=1, max_length=300)],
    session: SessionDep,
    current_user: CurrentUserDep,
) -> MealsByDishRead:
    user_id = _require_user_id(current_user)
    normalized_dish_name = dish_name.strip()
    if not normalized_dish_name:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="dishName must not be empty",
        )

    statement = (
        select(MealEntry)
        .where(
            MealEntry.user_id == user_id,
            func.lower(MealEntry.dish_name) == normalized_dish_name.lower(),
        )
        .order_by(MealEntry.time.desc(), MealEntry.id.desc())
    )
    meals = session.exec(statement).all()
    if not meals:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No meals found for dishName",
        )

    return MealsByDishRead(
        dish_name=meals[0].dish_name,
        meals=[_serialize_meal(meal) for meal in meals],
    )
