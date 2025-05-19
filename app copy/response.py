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