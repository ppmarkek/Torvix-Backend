from collections.abc import Iterator

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


def test_dish_names_and_get_meals_by_dish_name(client_with_stats_db: TestClient) -> None:
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
    for payload in payloads:
        response = client_with_stats_db.post("/stats/meals", json=payload)
        assert response.status_code == 201

    dish_names_response = client_with_stats_db.get("/stats/dish-names")
    assert dish_names_response.status_code == 200
    assert dish_names_response.json() == {"dishNames": ["Pasta", "Salad"]}

    by_dish_response = client_with_stats_db.get("/stats/dishes", params={"dishName": "pasta"})
    assert by_dish_response.status_code == 200
    by_dish_body = by_dish_response.json()
    assert by_dish_body["dishName"] == "Pasta"
    assert len(by_dish_body["meals"]) == 2

    missing_response = client_with_stats_db.get("/stats/dishes", params={"dishName": "Soup"})
    assert missing_response.status_code == 404
    assert missing_response.json() == {"detail": "No meals found for dishName"}
