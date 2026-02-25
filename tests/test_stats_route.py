from collections.abc import Callable, Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from app.api.routes.auth import get_current_user
from app.db.session import get_session
from app.main import app
from app.models.user import User


@pytest.fixture
def client_with_stats_db() -> Iterator[TestClient]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        user = User(
            email="stats@test.dev",
            name="Stats User",
            password_hash="hashed",
        )
        session.add(user)
        session.commit()

    def get_test_session():
        with Session(engine) as session:
            yield session

    def get_test_user() -> User:
        with Session(engine) as session:
            user = session.exec(select(User).where(User.email == "stats@test.dev")).first()
            assert user is not None
            return user

    app.dependency_overrides[get_session] = get_test_session
    app.dependency_overrides[get_current_user] = get_test_user

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()


@pytest.fixture
def client_with_multi_user_stats_db() -> Iterator[tuple[TestClient, Callable[[str], None]]]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    first_email = "stats-one@test.dev"
    second_email = "stats-two@test.dev"
    with Session(engine) as session:
        session.add(
            User(
                email=first_email,
                name="Stats User One",
                password_hash="hashed",
            )
        )
        session.add(
            User(
                email=second_email,
                name="Stats User Two",
                password_hash="hashed",
            )
        )
        session.commit()

    current_email = {"value": first_email}

    def set_current_user(email: str) -> None:
        current_email["value"] = email

    def get_test_session():
        with Session(engine) as session:
            yield session

    def get_test_user() -> User:
        with Session(engine) as session:
            user = session.exec(select(User).where(User.email == current_email["value"])).first()
            assert user is not None
            return user

    app.dependency_overrides[get_session] = get_test_session
    app.dependency_overrides[get_current_user] = get_test_user

    with TestClient(app) as client:
        yield client, set_current_user

    app.dependency_overrides.clear()


def test_create_meal_and_get_daily_statistics(client_with_stats_db: TestClient) -> None:
    payload = {
        "time": "2026-02-22T08:30:00Z",
        "dishName": "Omelette",
        "totalWeight": 260,
        "totalMacros": {
            "calories": 480,
            "protein": 25.5,
            "fat": 30.2,
            "fatSaturated": 8.4,
            "carbs": 14.5,
            "fiber": 2.1,
            "sugar": 3.2,
        },
        "ingredients": [
            {
                "name": "Egg",
                "quantity": 3,
                "weightPerUnit": 50,
                "macrosPer100g": {
                    "calories": 155,
                    "protein": 13,
                    "fat": 11,
                    "carbs": 1.1,
                    "fiber": 0,
                },
            }
        ],
    }
    create_response = client_with_stats_db.post("/stats/meals", json=payload)

    assert create_response.status_code == 201
    created_meal = create_response.json()
    assert created_meal["dishName"] == "Omelette"
    assert created_meal["totalMacros"]["fatSaturated"] == 8.4
    assert created_meal["ingredients"][0]["name"] == "Egg"

    stats_response = client_with_stats_db.get("/stats")
    assert stats_response.status_code == 200
    body = stats_response.json()
    assert len(body["days"]) == 1
    assert body["days"][0]["day"] == "2026-02-22"
    assert len(body["days"][0]["meals"]) == 1
    assert body["days"][0]["meals"][0]["dishName"] == "Omelette"

    daily_response = client_with_stats_db.get("/stats/days/2026-02-22/meals")
    assert daily_response.status_code == 200
    daily_body = daily_response.json()
    assert daily_body["day"] == "2026-02-22"
    assert len(daily_body["meals"]) == 1
    assert daily_body["meals"][0]["dishName"] == "Omelette"

    empty_daily_response = client_with_stats_db.get("/stats/days/2026-02-21/meals")
    assert empty_daily_response.status_code == 200
    assert empty_daily_response.json() == {"day": "2026-02-21", "meals": []}


def test_dish_names_and_get_meals_by_dish_id(client_with_stats_db: TestClient) -> None:
    payloads = [
        {
            "time": "2026-02-22T08:30:00",
            "dishName": "Pasta",
            "totalWeight": 300,
            "totalMacros": {
                "calories": 510,
                "protein": 20,
                "fat": 11,
                "carbs": 80,
                "fiber": 4,
            },
            "ingredients": [],
        },
        {
            "time": "2026-02-22T14:40:00",
            "dishName": "Pasta",
            "totalWeight": 320,
            "totalMacros": {
                "calories": 530,
                "protein": 22,
                "fat": 12,
                "carbs": 83,
                "fiber": 4,
            },
            "ingredients": [],
        },
        {
            "time": "2026-02-23T09:15:00",
            "dishName": "Salad",
            "totalWeight": 180,
            "totalMacros": {
                "calories": 190,
                "protein": 6,
                "fat": 9,
                "carbs": 18,
                "fiber": 5,
            },
            "ingredients": [],
        },
    ]
    created_ids: list[int] = []
    for payload in payloads:
        response = client_with_stats_db.post("/stats/meals", json=payload)
        assert response.status_code == 201
        created_ids.append(response.json()["id"])

    dish_names_response = client_with_stats_db.get("/stats/dish-names")
    assert dish_names_response.status_code == 200
    assert dish_names_response.json() == {
        "dishNames": [
            {"id": created_ids[1], "dishName": "Pasta"},
            {"id": created_ids[0], "dishName": "Pasta"},
            {"id": created_ids[2], "dishName": "Salad"},
        ]
    }

    by_dish_response = client_with_stats_db.get(
        "/stats/dishes",
        params={"dishId": created_ids[1]},
    )
    assert by_dish_response.status_code == 200
    by_dish_body = by_dish_response.json()
    assert by_dish_body["dishId"] == created_ids[1]
    assert by_dish_body["dishName"] == "Pasta"
    assert len(by_dish_body["meals"]) == 1
    assert by_dish_body["meals"][0]["id"] == created_ids[1]

    missing_response = client_with_stats_db.get("/stats/dishes", params={"dishId": 999999})
    assert missing_response.status_code == 404
    assert missing_response.json() == {"detail": "Dish not found"}


def test_delete_day_removes_all_meals(client_with_stats_db: TestClient) -> None:
    payloads = [
        {
            "time": "2026-02-20T08:30:00",
            "dishName": "Soup",
            "totalWeight": 250,
            "totalMacros": {
                "calories": 220,
                "protein": 10,
                "fat": 7,
                "carbs": 28,
                "fiber": 3,
            },
            "ingredients": [],
        },
        {
            "time": "2026-02-20T12:10:00",
            "dishName": "Rice",
            "totalWeight": 200,
            "totalMacros": {
                "calories": 260,
                "protein": 5,
                "fat": 3,
                "carbs": 52,
                "fiber": 1,
            },
            "ingredients": [],
        },
    ]
    for payload in payloads:
        response = client_with_stats_db.post("/stats/meals", json=payload)
        assert response.status_code == 201

    delete_response = client_with_stats_db.delete("/stats/days/2026-02-20")
    assert delete_response.status_code == 204

    day_response = client_with_stats_db.get("/stats/days/2026-02-20/meals")
    assert day_response.status_code == 200
    assert day_response.json() == {"day": "2026-02-20", "meals": []}

    second_delete = client_with_stats_db.delete("/stats/days/2026-02-20")
    assert second_delete.status_code == 404
    assert second_delete.json() == {"detail": "Statistics day not found"}


def test_delete_single_meal_in_day(client_with_stats_db: TestClient) -> None:
    first_payload = {
        "time": "2026-02-24T08:30:00",
        "dishName": "Toast",
        "totalWeight": 120,
        "totalMacros": {
            "calories": 290,
            "protein": 8,
            "fat": 9,
            "carbs": 41,
            "fiber": 2,
        },
        "ingredients": [],
    }
    second_payload = {
        "time": "2026-02-24T13:00:00",
        "dishName": "Fish",
        "totalWeight": 180,
        "totalMacros": {
            "calories": 310,
            "protein": 33,
            "fat": 16,
            "carbs": 3,
            "fiber": 0,
        },
        "ingredients": [],
    }

    first_meal = client_with_stats_db.post("/stats/meals", json=first_payload)
    assert first_meal.status_code == 201
    first_meal_id = first_meal.json()["id"]

    second_meal = client_with_stats_db.post("/stats/meals", json=second_payload)
    assert second_meal.status_code == 201
    second_meal_id = second_meal.json()["id"]

    delete_first = client_with_stats_db.delete(
        f"/stats/days/2026-02-24/meals/{first_meal_id}"
    )
    assert delete_first.status_code == 204

    day_after_first_delete = client_with_stats_db.get("/stats/days/2026-02-24/meals")
    assert day_after_first_delete.status_code == 200
    day_body = day_after_first_delete.json()
    assert len(day_body["meals"]) == 1
    assert day_body["meals"][0]["id"] == second_meal_id

    missing_meal_delete = client_with_stats_db.delete(
        f"/stats/days/2026-02-24/meals/{first_meal_id}"
    )
    assert missing_meal_delete.status_code == 404
    assert missing_meal_delete.json() == {"detail": "Meal not found in this day"}

    delete_second = client_with_stats_db.delete(
        f"/stats/days/2026-02-24/meals/{second_meal_id}"
    )
    assert delete_second.status_code == 204

    empty_day = client_with_stats_db.get("/stats/days/2026-02-24/meals")
    assert empty_day.status_code == 200
    assert empty_day.json() == {"day": "2026-02-24", "meals": []}


def test_stats_are_isolated_per_user(
    client_with_multi_user_stats_db: tuple[TestClient, Callable[[str], None]]
) -> None:
    client, set_current_user = client_with_multi_user_stats_db

    first_user_email = "stats-one@test.dev"
    second_user_email = "stats-two@test.dev"
    day_value = "2026-02-25"

    set_current_user(first_user_email)
    first_create = client.post(
        "/stats/meals",
        json={
            "time": f"{day_value}T08:00:00",
            "dishName": "User One Meal",
            "totalWeight": 250,
            "totalMacros": {
                "calories": 350,
                "protein": 20,
                "fat": 10,
                "carbs": 40,
                "fiber": 5,
            },
            "ingredients": [],
        },
    )
    assert first_create.status_code == 201
    first_meal_id = first_create.json()["id"]

    set_current_user(second_user_email)
    second_create = client.post(
        "/stats/meals",
        json={
            "time": f"{day_value}T12:00:00",
            "dishName": "User Two Meal",
            "totalWeight": 300,
            "totalMacros": {
                "calories": 420,
                "protein": 28,
                "fat": 14,
                "carbs": 45,
                "fiber": 6,
            },
            "ingredients": [],
        },
    )
    assert second_create.status_code == 201

    first_user_delete_attempt = client.delete(
        f"/stats/days/{day_value}/meals/{first_meal_id}"
    )
    assert first_user_delete_attempt.status_code == 404

    set_current_user(first_user_email)
    first_day = client.get(f"/stats/days/{day_value}/meals")
    assert first_day.status_code == 200
    first_day_meals = first_day.json()["meals"]
    assert len(first_day_meals) == 1
    assert first_day_meals[0]["id"] == first_meal_id
    assert first_day_meals[0]["dishName"] == "User One Meal"

    delete_first_day = client.delete(f"/stats/days/{day_value}")
    assert delete_first_day.status_code == 204

    set_current_user(second_user_email)
    second_day = client.get(f"/stats/days/{day_value}/meals")
    assert second_day.status_code == 200
    second_day_meals = second_day.json()["meals"]
    assert len(second_day_meals) == 1
    assert second_day_meals[0]["dishName"] == "User Two Meal"
