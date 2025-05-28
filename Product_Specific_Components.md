# Product-Specific Components Documentation

## Table of Contents
1. [Table Extraction](#1-table-extraction)
2. [Crew Setup](#2-crew-setup)
3. [Data Validation](#3-data-validation)
4. [Product-Specific Configuration](#4-product-specific-configuration)

## 1. Table Extraction

### 1.1 Product-Specific Headers
```python
# Task Management Product Headers
START_HEADER_PATTERN = 'Release Readiness Critical Metrics (Previous/Current):'
END_HEADER_PATTERN = 'Release Readiness Functional teams Deliverables Checklist:'

# Expected Metrics for Task Management
EXPECTED_METRICS = [
    "Open ALL RRR Defects",
    "Open Security Defects",
    "All Open Defects (T-1)",
    "All Security Open Defects",
    "Load/Performance",
    "E2E Test Coverage",
    "Automation Test Coverage",
    "Unit Test Coverage",
    "Defect Closure Rate",
    "Regression Issues",
    "Customer Specific Testing (UAT)"
]
```

### 1.2 Table Extraction Function
```python
def locate_table(text: str, start_header: str, end_header: str) -> str:
    """
    Locates and extracts table data between specified headers in text.
    
    Args:
        text (str): Full text content
        start_header (str): Starting header pattern
        end_header (str): Ending header pattern
        
    Returns:
        str: Extracted table text
        
    Raises:
        ValueError: If headers not found or no data between headers
    """
    start_index = text.find(start_header)
    end_index = text.find(end_header)
    
    if start_index == -1:
        raise ValueError(f'Header {start_header} not found in text')
    if end_index == -1:
        raise ValueError(f'Header {end_header} not found in text')
        
    table_text = text[start_index:end_index].strip()
    if not table_text:
        raise ValueError(f"No metrics table data found between headers")
        
    return table_text
```

### 1.3 Product-Specific Table Structure
1. **Task Management Table Format**
   - ATLS/BTLS split for defect metrics
   - Client-specific UAT sections
   - Performance metrics with thresholds

2. **Required Sections**
   - Defect metrics (ATLS/BTLS)
   - Performance metrics
   - Testing coverage
   - Quality metrics
   - Customer testing

## 2. Crew Setup

### 2.1 Data Structuring Crew
```python
structurer = Agent(
    role="Task Management Data Architect",
    goal="Structure raw Task Management release data into VALID JSON format",
    backstory="Expert in transforming Task Management metrics into clean JSON structures",
    llm=llm,
    verbose=True,
    memory=True,
)

validated_structure_task = Task(
    description=f"""Convert this release data to STRICT JSON:
{extracted_text}

RULES:
1. Output MUST be valid JSON only
2. Use this EXACT structure:
{{
    "metrics": {{
        "Open ALL RRR Defects": {{"ATLS": [{{"version": "{versions[0]}", "value": N, "status": "TEXT"}}, ...], "BTLS": [...]}},
        "Open Security Defects": {{"ATLS": [...], "BTLS": [...]}},
        "All Open Defects (T-1)": {{"ATLS": [...], "BTLS": [...]}},
        "All Security Open Defects": {{"ATLS": [...], "BTLS": [...]}},
        "Load/Performance": {{"ATLS": [...], "BTLS": [...]}},
        "E2E Test Coverage": [{{"version": "{versions[0]}", "value": N, "status": "TEXT"}}, ...],
        "Automation Test Coverage": [...],
        "Unit Test Coverage": [...],
        "Defect Closure Rate": [...],
        "Regression Issues": [...],
        "Customer Specific Testing (UAT)": {{
            "RBS": [{{"version": "{versions[0]}", "pass_count": N, "fail_count": M, "status": "TEXT"}}, ...],
            "Tesco": [...],
            "Belk": [...]
        }}
    }}
}}""",
    agent=structurer,
    async_execution=False,
    expected_output="Valid JSON string with no extra text"
)
```

### 2.2 Analysis Crew
```python
analyst = Agent(
    role="Task Management Trend Analyst",
    goal="Add accurate trends to Task Management metrics data and maintain valid JSON",
    backstory="Data scientist specializing in Task Management metric analysis",
    llm=llm,
    verbose=True,
    memory=True,
)

analysis_task = Task(
    description=f"""Enhance metrics JSON with trends:
1. Input is JSON from Data Structurer
2. Add 'trend' field to each metric item
3. Output MUST be valid JSON
4. For metrics except Customer Specific Testing (UAT):
   - Sort items by version
   - Compute % change: ((current_value - previous_value) / previous_value) * 100
   - Set trend based on change percentage
5. For Customer Specific Testing (UAT):
   - Compute pass rate: pass_count / (pass_count + fail_count) * 100
   - Calculate trend based on pass rate change
6. Ensure all metrics are included
7. Validate JSON syntax""",
    agent=analyst,
    async_execution=True,
    context=[validated_structure_task]
)
```

### 2.3 Visualization Crew
```python
visualizer = Agent(
    role="Task Management Data Visualizer",
    goal="Generate consistent visualizations for Task Management metrics",
    backstory="Expert in generating Python plots for Task Management metrics",
    llm=llm,
    verbose=True,
    memory=True,
)

visualization_task = Task(
    description=f"""Create visualizations for Task Management metrics:
1. Generate exactly 10 visualizations:
   - ATLS/BTLS comparison charts
   - Coverage trend charts
   - Performance metrics
   - UAT results
2. Use consistent styling
3. Include proper labels and legends
4. Save as PNG files""",
    agent=visualizer,
    context=[analysis_task]
)
```

## 3. Data Validation

### 3.1 Metric Validation Function
```python
def validate_metrics(metrics: Dict[str, Any]) -> bool:
    """
    Validates the structure and content of Task Management metrics data.
    
    Args:
        metrics (Dict[str, Any]): Metrics data to validate
        
    Returns:
        bool: True if valid, False otherwise
    """
    # Check basic structure
    if not metrics or 'metrics' not in metrics:
        return False
        
    # Validate ATLS/BTLS metrics
    for metric in EXPECTED_METRICS[:5]:
        if metric not in metrics['metrics']:
            return False
        data = metrics['metrics'][metric]
        if not isinstance(data, dict) or 'ATLS' not in data or 'BTLS' not in data:
            return False
            
    # Validate UAT metrics
    uat_data = metrics['metrics'].get("Customer Specific Testing (UAT)")
    if not isinstance(uat_data, dict):
        return False
    for client in ['RBS', 'Tesco', 'Belk']:
        if client not in uat_data:
            return False
            
    # Validate other metrics
    for metric in EXPECTED_METRICS[5:10]:
        if metric not in metrics['metrics']:
            return False
            
    return True
```

### 3.2 Product-Specific Validation Rules

#### 3.2.1 ATLS/BTLS Metrics
```python
def validate_atls_btls_metrics(data: Dict) -> bool:
    """
    Validates ATLS/BTLS metrics for Task Management.
    
    Rules:
    1. Both ATLS and BTLS sections must exist
    2. Values must be non-negative
    3. Status must be valid
    4. At least one non-zero value per section
    """
    if not isinstance(data, dict):
        return False
        
    for section in ['ATLS', 'BTLS']:
        if section not in data:
            return False
        items = data[section]
        if not isinstance(items, list) or len(items) < 2:
            return False
        has_non_zero = False
        for item in items:
            if not validate_metric_item(item):
                return False
            if float(item['value']) > 0:
                has_non_zero = True
        if not has_non_zero:
            return False
            
    return True
```

#### 3.2.2 UAT Metrics
```python
def validate_uat_metrics(data: Dict) -> bool:
    """
    Validates UAT metrics for Task Management.
    
    Rules:
    1. All clients must be present
    2. Pass/fail counts must be non-negative
    3. At least one non-zero count per client
    4. Status must be valid
    """
    required_clients = ['RBS', 'Tesco', 'Belk']
    if not all(client in data for client in required_clients):
        return False
        
    for client in required_clients:
        items = data[client]
        if not isinstance(items, list) or len(items) < 2:
            return False
        has_non_zero = False
        for item in items:
            if not validate_uat_item(item):
                return False
            if float(item['pass_count']) > 0 or float(item['fail_count']) > 0:
                has_non_zero = True
        if not has_non_zero:
            return False
            
    return True
```

## 4. Product-Specific Configuration

### 4.1 Metric Thresholds
```python
METRIC_THRESHOLDS = {
    "Open ALL RRR Defects": {
        "ATLS": {"RISK": 10, "MEDIUM_RISK": 5},
        "BTLS": {"RISK": 12, "MEDIUM_RISK": 6}
    },
    "E2E Test Coverage": {"MINIMUM": 80},
    "Automation Test Coverage": {"MINIMUM": 70},
    "Unit Test Coverage": {"MINIMUM": 85}
}
```

### 4.2 Status Definitions
```python
STATUS_DEFINITIONS = {
    "ON TRACK": "All metrics within acceptable ranges",
    "MEDIUM RISK": "Some metrics approaching thresholds",
    "RISK": "Multiple metrics exceeding thresholds",
    "NEEDS REVIEW": "Requires immediate attention"
}
```

### 4.3 Trend Calculations
```python
def calculate_trend(current: float, previous: float) -> str:
    """
    Calculates trend for Task Management metrics.
    
    Args:
        current (float): Current value
        previous (float): Previous value
        
    Returns:
        str: Trend indicator with percentage
    """
    if previous == 0 or abs(current - previous) < 0.01:
        return "→"
        
    pct_change = ((current - previous) / previous) * 100
    if abs(pct_change) < 1:
        return "→"
    elif pct_change > 0:
        return f"↑ ({abs(pct_change):.1f}%)"
    else:
        return f"↓ ({abs(pct_change):.1f}%)"
``` 