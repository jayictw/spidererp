from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).resolve().parents[2] / '.env'),
        env_file_encoding='utf-8',
        extra='ignore',
    )

    app_name: str = Field(default='公开网站线索解析调试台', alias='APP_NAME')
    app_env: str = Field(default='development', alias='APP_ENV')
    debug: bool = Field(default=True, alias='DEBUG')
    secret_key: str = Field(default='change_me', alias='SECRET_KEY')

    host: str = Field(default='127.0.0.1', alias='HOST')
    port: int = Field(default=8000, alias='PORT')
    database_url: str = Field(default='sqlite:///./lead_parser.db', alias='DATABASE_URL')

    n8n_webhook_url: str = Field(default='', alias='N8N_WEBHOOK_URL')
    n8n_token: str = Field(default='', alias='N8N_TOKEN')
    erp_base_url: str = Field(default='', alias='ERP_BASE_URL')
    erp_intake_token: str = Field(default='', alias='ERP_INTAKE_TOKEN')

    crawler_default_timeout: int = Field(default=20, alias='CRAWLER_DEFAULT_TIMEOUT')
    crawler_max_retries: int = Field(default=2, alias='CRAWLER_MAX_RETRIES')
    crawler_per_domain_delay: int = Field(default=2, alias='CRAWLER_PER_DOMAIN_DELAY')
    crawler_ssl_verify: bool = Field(default=True, alias='CRAWLER_SSL_VERIFY')

    csv_export_dir: str = Field(default='./exports', alias='CSV_EXPORT_DIR')
    log_level: str = Field(default='INFO', alias='LOG_LEVEL')


@lru_cache
def get_settings() -> Settings:
    return Settings()
