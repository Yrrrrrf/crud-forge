from pydantic import BaseModel, Field
from enum import Enum
from typing import Dict
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging
import re

# * NOT USED BUT ALLOW A SHORTER IMPORT (from forge.utils import *)
from forge.utils.sql_types import SQL_TYPE_MAPPING, get_eq_type


class LogLevel(str, Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"

class Config(BaseModel):
    PROJECT_NAME: str = Field(..., description="The name of your project")
    VERSION: str = Field(default="0.1.0", description="The version of your project")
    DESCRIPTION: str | None = Field(default=None, description="A brief description of your project")
    AUTHOR: str | None = Field(default=None)
    EMAIL: str | None = Field(default=None)  # contact mail
    LICENSE: str | None = Field(default='MIT', description="The license for the project")
    LICENSE_URL: str | None = Field(default='https://choosealicense.com/licenses/mit/')
    LOG_LEVEL: LogLevel = Field(default=LogLevel.INFO)

    def set_app_data(self, app: FastAPI) -> None:
        app.title = self.PROJECT_NAME
        app.description = self.DESCRIPTION
        app.version = self.VERSION
        app.contact = {"name": self.AUTHOR, "email": self.EMAIL}
        app.license_info = {"name": self.LICENSE, "url": self.LICENSE_URL}

    def setup_logging(self):
        logging.basicConfig(level=self.LOG_LEVEL)
        formatter = ColoredAccessFormatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        for handler in logging.root.handlers:
            handler.setFormatter(formatter)


class ColoredAccessFormatter(logging.Formatter):
    method_colors: Dict[str, str] = {
        "GET": "\033[94m",    # Blue
        "PUT": "\033[93m",    # Yellow
        "DELETE": "\033[91m", # Red
        "POST": "\033[92m",   # Green
        "RESET": "\033[0m"    # Reset color
    }

    def format(self, record: logging.LogRecord) -> str:
        return re.sub(
            r'(' + '|'.join(self.method_colors.keys()) + r' )',
            lambda match: f'{self.method_colors[match.group()]}{match.group()}{self.method_colors["RESET"]}',
            super().format(record)
        )

def allow_all_middleware(app: FastAPI) -> None:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
