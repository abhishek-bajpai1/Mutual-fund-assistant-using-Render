# pyre-ignore-all-errors
from datetime import datetime
# Trigger Pyright refresh
from pydantic import BaseModel, Field  # type: ignore

class SchemeData(BaseModel):
    scheme_id: str = Field(..., description="Slug derived from the URL")
    scheme_name: str = Field(..., description="Full scheme name (Direct Growth variant)")
    amc_name: str = Field(..., description="Asset management company name")
    fund_category: str = Field(..., description="e.g., Large Cap, ELSS, Liquid, Hybrid")
    
    expense_ratio: str = Field(..., description="Current expense ratio (Direct Growth)")
    minimum_sip: str = Field(..., description="Minimum SIP amount")
    minimum_lumpsum: str = Field(..., description="Minimum one-time investment")
    exit_load: str = Field(..., description="Exit load rules and duration")
    lock_in_period: str = Field(..., description="Applicable for ELSS (e.g., 3 years)")
    
    riskometer_category: str = Field(..., description="Risk level (e.g., Moderate, High, Very High)")
    benchmark_index: str = Field(..., description="Official benchmark index")
    
    source_url: str = Field(..., description="Canonical scheme URL")
    last_updated: str = Field(default_factory=lambda: datetime.utcnow().isoformat())