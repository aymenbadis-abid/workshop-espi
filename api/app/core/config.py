from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    database_url: str
    mqtt_host: str = "mosquitto"
    mqtt_port: int = 8883
    mqtt_api_username: str
    mqtt_api_password: str
    mqtt_topic_base: str = "sentinelx/g6"
    mqtt_device_base: str = "sentinelx/esp32-01"
    mqtt_ca_cert: str = "/certs/ca.crt"
    anomaly_model_path: str = "/app/ml_training/models/isolation_forest.joblib"
    room_temp_model_path: str | None = None
    room_hum_model_path: str | None = None
    room_couple_model_path: str | None = None
    api_cors_origins: str = "http://localhost:5173,http://127.0.0.1:8080"
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    admin_email: str
    admin_password: str
    vision_token: str

    def _model_file(self, override: str | None, filename: str) -> Path:
        if override:
            return Path(override)
        return Path(self.anomaly_model_path).parent / filename

    @property
    def room_temp_path(self) -> Path:
        return self._model_file(self.room_temp_model_path, "room_temp.joblib")

    @property
    def room_hum_path(self) -> Path:
        return self._model_file(self.room_hum_model_path, "room_hum.joblib")

    @property
    def room_couple_path(self) -> Path:
        return self._model_file(self.room_couple_model_path, "room_couple.joblib")

    @property
    def cors_origins(self) -> list[str]:
        return [item.strip() for item in self.api_cors_origins.split(",") if item.strip()]


settings = Settings()
