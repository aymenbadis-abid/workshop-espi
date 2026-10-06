from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    database_url: str
    mqtt_host: str = "mosquitto"
    mqtt_port: int = 8883
    mqtt_api_username: str
    mqtt_api_password: str
    mqtt_topic_base: str = "sentinelx/g6"
    mqtt_ca_cert: str = "/certs/ca.crt"
    anomaly_model_path: str = "/app/ml_training/models/isolation_forest.joblib"
    api_cors_origins: str = "http://localhost:5173,http://127.0.0.1:8080"

    @property
    def cors_origins(self) -> list[str]:
        return [item.strip() for item in self.api_cors_origins.split(",") if item.strip()]


settings = Settings()
