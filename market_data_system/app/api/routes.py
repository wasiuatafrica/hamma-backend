from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
import secrets
from typing import List, Dict, Any
from datetime import datetime

from common.utils.config import settings
from common.db.mongodb import mongodb
from common.db.postgres import postgres_db
from common.utils.market_utils import is_market_open
from collectors.ngx_collector import ngx_collector
from collectors.tv_collector import tv_collector
from collectors.data_merger import data_merger
from processors.asset_classifier import asset_classifier
from processors.signal_generator import signal_generator
from processors.chart_processor import chart_processor
from tasks.celery_app import app as celery_app

router = APIRouter()
security = HTTPBasic()


def get_current_username(credentials: HTTPBasicCredentials = Depends(security)):
    """Validate HTTP Basic Auth credentials."""
    correct_username = secrets.compare_digest(
        credentials.username, settings.dashboard_username
    )
    correct_password = secrets.compare_digest(
        credentials.password, settings.dashboard_password
    )

    if not (correct_username and correct_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )

    return credentials.username


@router.get("/status", response_model=Dict[str, Any])
async def get_system_status(username: str = Depends(get_current_username)):
    """Get the current system status."""
    try:
        # Get service statuses from MongoDB
        services = list(mongodb.system_status_collection.find({}, {"_id": 0}))

        # Check if market is open
        market_open = is_market_open()

        # Get active stocks count
        active_stocks = postgres_db.get_active_stocks()

        # Get performance metrics
        performance = list(
            mongodb.performance_metrics_collection.find({}, {"_id": 0})
            .sort([("timestamp", -1)])
            .limit(20)
        )

        # Get recent errors
        errors = list(
            mongodb.error_log_collection.find(
                {}, {"_id": 0, "stack_trace": 0, "data": 0}
            )
            .sort([("timestamp", -1)])
            .limit(10)
        )

        # Get recent notifications
        notifications = list(
            mongodb.notification_log_collection.find({}, {"_id": 0, "body": 0})
            .sort([("timestamp", -1)])
            .limit(10)
        )

        return {
            "timestamp": datetime.now().isoformat(),
            "market_open": market_open,
            "active_symbols_count": len(active_stocks),
            "services": services,
            "recent_performance": performance,
            "recent_errors": errors,
            "recent_notifications": notifications,
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error getting system status: {str(e)}"
        )


@router.get("/symbols", response_model=List[Dict[str, Any]])
async def get_symbol_status(username: str = Depends(get_current_username)):
    """Get the status of all symbols."""
    try:
        # Get symbol statuses from MongoDB
        symbols = list(mongodb.symbol_status_collection.find({}, {"_id": 0}))
        return symbols
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error getting symbol status: {str(e)}"
        )


@router.post("/run/{task_name}", response_model=Dict[str, Any])
async def run_task(task_name: str, username: str = Depends(get_current_username)):
    """Run a specific task on demand."""
    try:
        result = None
        message = ""

        if task_name == "ngx":
            result = ngx_collector.run()
            message = "NGX data collection task started"
        elif task_name == "tv":
            result = tv_collector.run()
            message = "TradingView data collection task started"
        elif task_name == "merge":
            result = data_merger.run()
            message = "Data merge task started"
        elif task_name == "classify":
            result = asset_classifier.run()
            message = "Asset classification task started"
        elif task_name == "signals":
            result = signal_generator.run()
            message = "Signal generation task started"
        elif task_name == "daily_charts":
            result = chart_processor.update_daily_charts()
            message = "Daily chart update task started"
        elif task_name == "minute_charts":
            result = chart_processor.update_minute_charts()
            message = "Minute chart update task started"
        else:
            raise HTTPException(status_code=400, detail=f"Unknown task: {task_name}")

        return {
            "task": task_name,
            "message": message,
            "timestamp": datetime.now().isoformat(),
            "success": result is not None,
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error running task {task_name}: {str(e)}"
        )


@router.get("/logs/recent", response_model=Dict[str, Any])
async def get_recent_logs(username: str = Depends(get_current_username)):
    """Get recent logs from MongoDB."""
    try:
        # Get recent errors
        errors = list(
            mongodb.error_log_collection.find({}, {"_id": 0})
            .sort([("timestamp", -1)])
            .limit(50)
        )

        # Get recent notifications
        notifications = list(
            mongodb.notification_log_collection.find({}, {"_id": 0})
            .sort([("timestamp", -1)])
            .limit(50)
        )

        # Get recent performance metrics
        performance = list(
            mongodb.performance_metrics_collection.find({}, {"_id": 0})
            .sort([("timestamp", -1)])
            .limit(50)
        )

        return {
            "errors": errors,
            "notifications": notifications,
            "performance": performance,
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error getting recent logs: {str(e)}"
        )


@router.get("/health", response_model=Dict[str, str])
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "timestamp": datetime.now().isoformat()}


@router.get("/errors/{error_id}", response_model=Dict[str, Any])
async def get_error_details(
    error_id: str, username: str = Depends(get_current_username)
):
    """Get details of a specific error."""
    try:
        from bson import ObjectId

        # Convert string ID to ObjectId
        obj_id = ObjectId(error_id)

        # Get error details from MongoDB
        error = mongodb.error_log_collection.find_one({"_id": obj_id})

        if not error:
            raise HTTPException(status_code=404, detail="Error not found")

        # Convert ObjectId to string for JSON serialization
        error["_id"] = str(error["_id"])

        return error
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error getting error details: {str(e)}"
        )


@router.get("/performance", response_model=Dict[str, Any])
async def get_performance_metrics(username: str = Depends(get_current_username)):
    """Get performance metrics for charting."""
    try:
        # Get performance metrics from MongoDB
        metrics = list(
            mongodb.performance_metrics_collection.find({}, {"_id": 0})
            .sort([("timestamp", -1)])
            .limit(100)
        )

        # Group by component and operation
        grouped_metrics = {}
        for metric in metrics:
            key = f"{metric['component']}-{metric['operation']}"
            if key not in grouped_metrics:
                grouped_metrics[key] = []

            grouped_metrics[key].append(
                {
                    "timestamp": metric["timestamp"].isoformat(),
                    "duration": metric["duration_seconds"],
                    "data_points": metric.get("data_points", 0),
                }
            )

        return {"metrics": metrics, "grouped_metrics": grouped_metrics}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error getting performance metrics: {str(e)}"
        )


@router.get("/symbols/inactive", response_model=List[Dict[str, Any]])
async def get_inactive_symbols(username: str = Depends(get_current_username)):
    """Get all inactive symbols."""
    try:
        # Get inactive symbols from MongoDB
        symbols = list(
            mongodb.symbol_status_collection.find({"is_active": False}, {"_id": 0})
        )
        return symbols
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error getting inactive symbols: {str(e)}"
        )
