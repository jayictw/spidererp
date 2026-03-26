from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import select

from app.api.v1.crawler_routes import router as crawler_router
from app.api.v1.rules_routes import router as rules_actions_router
from app.api.v1.router import router as api_v1_router
from app.core.config import get_settings
from app.core.response import error_response
from app.db.init_db import init_database
from app.db.session import create_session_factory
from app.models import Sample, SystemConfig
from app.schemas.domain import JobCreate, SampleRead, SystemConfigItem
from app.services.domain_service import create_job as create_job_service, upsert_config as upsert_config_service
from app.services.seed_service import build_seed_preview
from app.services.trace_service import build_sample_trace_payload


def create_app(database_url: str | None = None) -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, debug=settings.debug)

    resolved_database_url = database_url or settings.database_url
    init_database(resolved_database_url)
    session_factory = create_session_factory(resolved_database_url)
    seed_preview = build_seed_preview()
    base_dir = Path(__file__).resolve().parent

    app.state.settings = settings
    app.state.session_factory = session_factory
    templates = Jinja2Templates(directory=str(base_dir / 'templates'))
    app.mount('/static', StaticFiles(directory=str(base_dir / 'static')), name='static')

    def _base_context(request: Request, title: str, nav: str) -> dict:
        return {
            'request': request,
            'page_title': title,
            'page_subtitle': 'MVP 后台页面',
            'page_kicker': '公开网站线索解析调试台',
            'active_nav': nav,
            'runtime_mode': settings.app_env,
        }

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):  # noqa: ARG001
        return JSONResponse(status_code=422, content=error_response('validation_error', 'request validation failed'))

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):  # noqa: ARG001
        if isinstance(exc.detail, dict) and 'success' in exc.detail:
            return JSONResponse(status_code=exc.status_code, content=exc.detail)
        if isinstance(exc.detail, dict):
            return JSONResponse(status_code=exc.status_code, content=exc.detail)
        return JSONResponse(status_code=exc.status_code, content=error_response('http_error', str(exc.detail)))

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):  # noqa: ARG001
        return JSONResponse(status_code=500, content=error_response('internal_error', str(exc)))

    app.include_router(api_v1_router)
    app.include_router(crawler_router)
    app.include_router(rules_actions_router)

    @app.get('/')
    async def root(request: Request):
        return templates.TemplateResponse(
            request=request,
            name='dashboard.html',
            context={
                **_base_context(request, 'Dashboard', 'dashboard'),
                'stats': [
                    {'label': '任务', 'value': str(len(seed_preview['jobs'])), 'note': 'seed preview'},
                    {'label': '规则', 'value': str(len(seed_preview['rules'])), 'note': 'seed preview'},
                    {'label': '样本', 'value': str(len(seed_preview['samples'])), 'note': 'seed preview'},
                    {'label': '审计', 'value': '1', 'note': 'bootstrap'},
                ],
                'jobs': [],
                'seed_preview': seed_preview['samples'],
                'readiness': [
                    '数据库初始化入口已就绪',
                    'seed 数据预览已就绪',
                    'robots.txt 检查入口已保留',
                    '限速与重试入口已保留',
                ],
            },
        )

    @app.get('/dashboard')
    async def dashboard_page(request: Request):
        return await root(request)

    @app.get('/jobs')
    async def jobs_page(request: Request):
        return templates.TemplateResponse(
            request=request,
            name='jobs.html',
            context={
                **_base_context(request, '任务列表', 'jobs'),
                'jobs': [],
                'filters': {},
                'job_seed_preview': [item['task_name'] for item in seed_preview['jobs']],
            },
        )

    @app.get('/jobs/new')
    async def job_new_page(request: Request):
        return templates.TemplateResponse(
            request=request,
            name='job_new.html',
            context={
                **_base_context(request, '新建任务', 'jobs'),
                'job_fields': {},
            },
        )

    @app.post('/jobs/new')
    async def job_new_submit(request: Request):
        form = await request.form()
        session = session_factory()
        try:
            payload = JobCreate(
                task_name=str(form.get('task_name', '')),
                crawl_scope=str(form.get('crawl_scope', 'public_web')),
                source_type=str(form.get('source_type', 'website')),
                keywords=[x.strip() for x in str(form.get('keywords', '')).split(',') if x.strip()],
                start_page=int(str(form.get('start_page', '1')) or '1'),
                max_pages=int(str(form.get('max_pages', '1')) or '1'),
                time_range=str(form.get('time_range', '')),
                include_domains=[x.strip() for x in str(form.get('include_domains', '')).split(',') if x.strip()],
                exclude_rules=[x.strip() for x in str(form.get('exclude_rules', '')).split(',') if x.strip()],
                rule_notes=str(form.get('rule_notes', '')),
                schedule_mode=str(form.get('schedule_mode', 'manual')),
                schedule_note=str(form.get('schedule_note', '')),
                n8n_webhook=str(form.get('n8n_webhook', '')),
                auto_push_n8n=str(form.get('auto_push_n8n', 'false')).lower() == 'true',
                enabled=str(form.get('enabled', 'true')).lower() == 'true',
                status='pending',
            )
            create_job_service(session, payload, operator='web_form')
        finally:
            session.close()
        return RedirectResponse(url='/jobs', status_code=303)

    @app.get('/rules')
    async def rules_page(request: Request):
        return templates.TemplateResponse(
            request=request,
            name='rules.html',
            context={
                **_base_context(request, '规则列表', 'rules'),
                'rules': [],
                'filters': {},
                'rule_seed_preview': seed_preview['rules'],
            },
        )

    @app.get('/rules/{rule_id}')
    async def rule_detail_page(request: Request, rule_id: int):
        return templates.TemplateResponse(
            request=request,
            name='rule_detail.html',
            context={
                **_base_context(request, f'规则详情 #{rule_id}', 'rules'),
                'rule': {},
                'rule_versions': [],
                'related_samples': [],
            },
        )

    @app.get('/samples')
    async def samples_page(request: Request):
        trace_sample_id_raw = request.query_params.get('trace_sample_id')
        trace_sample_id = int(trace_sample_id_raw) if trace_sample_id_raw and trace_sample_id_raw.isdigit() else None
        session = session_factory()
        trace_data = None
        trace_error = None
        try:
            sample_rows = session.execute(select(Sample).order_by(Sample.crawl_time.desc(), Sample.id.desc()).limit(50)).scalars().all()
            samples_data = [SampleRead.model_validate(item).model_dump(mode='json') for item in sample_rows]
            if trace_sample_id_raw and trace_sample_id is None:
                trace_error = {'error': 'invalid_trace_sample_id', 'message': 'trace_sample_id 无效'}
            if trace_sample_id is not None:
                try:
                    trace_data = build_sample_trace_payload(session, trace_sample_id)
                except HTTPException as exc:
                    if isinstance(exc.detail, dict):
                        error_code = str(exc.detail.get('error') or exc.detail.get('code') or 'trace_error')
                        error_message = str(exc.detail.get('message') or exc.detail.get('detail') or 'trace 加载失败')
                        trace_error = {'error': error_code, 'message': error_message}
                    else:
                        trace_error = {'error': 'trace_error', 'message': str(exc.detail)}
        finally:
            session.close()
        return templates.TemplateResponse(
            request=request,
            name='samples.html',
            context={
                **_base_context(request, '样本管理', 'samples'),
                'samples': samples_data,
                'filters': {},
                'normalized_schema_preview': {},
                'sample_seed_preview': seed_preview['samples'],
                'trace_data': trace_data,
                'trace_error': trace_error,
                'trace_sample_id': trace_sample_id,
            },
        )

    @app.get('/training-queue')
    async def training_queue_page(request: Request):
        return templates.TemplateResponse(
            request=request,
            name='training_queue.html',
            context={**_base_context(request, '训练队列', 'training-queue'), 'training_queue': [], 'filters': {}},
        )

    @app.get('/audit')
    async def audit_page(request: Request):
        return templates.TemplateResponse(
            request=request,
            name='audit.html',
            context={**_base_context(request, '审计日志', 'audit'), 'audit_logs': [], 'filters': {}},
        )

    @app.get('/config')
    async def config_page(request: Request):
        session = session_factory()
        try:
            config = session.get(SystemConfig, 1)
            config_snapshot = SystemConfigItem.model_validate(config).model_dump(mode='json') if config else {}
        finally:
            session.close()
        return templates.TemplateResponse(
            request=request,
            name='config.html',
            context={
                **_base_context(request, '系统配置', 'config'),
                'config': config_snapshot,
                'config_status': [
                    'ERP base URL 预留',
                    'n8n webhook 预留',
                    'Token 字段预留',
                    'robots 检查入口预留',
                ],
            },
        )

    @app.post('/config')
    async def config_submit(request: Request):
        form = await request.form()
        session = session_factory()
        try:
            payload = SystemConfigItem(
                erp_base_url=str(form.get('erp_base_url', '')),
                n8n_webhook=str(form.get('n8n_webhook', '')),
                n8n_token=str(form.get('n8n_token', '')),
                erp_intake_token=str(form.get('erp_intake_token', '')),
            )
            upsert_config_service(session, payload, operator='web_form')
        finally:
            session.close()
        return RedirectResponse(url='/config', status_code=303)

    return app


app = create_app()
