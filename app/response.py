from dataclasses import dataclass

@dataclass
class ModelResponse:
    code: int
    message: str
    result: str
    
    def to_dict(self):
        return {
            "code": self.code,
            "message": self.message,
            "result": self.result
        }
    
@dataclass
class BadRequest:
    error: str
    code: int = 400
    message: str = "Error!"

    def to_dict(self):
        return {
            "code":self.code,
            "message": self.message,
            "error":self.error
        }
    
from dataclasses import dataclass

@dataclass
class ResultResponse:
    apnea_count: int
    lowest_spo2: float
    lowest_spo2_visual: str

    def to_dict(self):
        return {
            "apnea_count": self.apnea_count,
            "lowest_spo2": self.lowest_spo2,
            "lowest_spo2_visual": self.lowest_spo2_visual
        }

@dataclass
class FixedModelResponse:
    code: int
    message: str
    result: ResultResponse

    def to_dict(self):
        return {
            "code": self.code,
            "message": self.message,
            "result": self.result.to_dict()
        }