from pydantic import BaseModel

class SnakeData(BaseModel):
    snake_size: int
    won: bool
    time_remaining: int

class SnakePayload(BaseModel):
    score: int
    completion_time: int
    data: SnakeData
