# RRR Analysis Tool - Application Usage Guide

## Table of Contents
1. [Getting Started](#1-getting-started)
2. [Installation](#2-installation)
3. [Configuration](#3-configuration)
4. [Basic Usage](#4-basic-usage)
5. [Advanced Features](#5-advanced-features)
6. [Troubleshooting](#6-troubleshooting)

## 1. Getting Started

### 1.1 Prerequisites
- Python 3.8 or higher
- Git
- Access to Azure OpenAI API
- PDF files containing Release Readiness Reports

### 1.2 System Requirements
- Minimum 4GB RAM
- 1GB free disk space
- Internet connection for API access

## 2. Installation

### 2.1 Clone the Repository
```bash
git clone <repository-url>
cd rrr-analysis-tool
```

### 2.2 Install Dependencies
```bash
pip install -r requirements.txt
```

### 2.3 Environment Setup
1. Create a `.env` file in the project root
2. Add the following environment variables:
```env
AZURE_OPENAI_API_KEY=your_api_key
AZURE_OPENAI_ENDPOINT=your_endpoint
AZURE_API_VERSION=your_api_version
DEPLOYMENT_NAME=your_deployment_name
```

## 3. Configuration

### 3.1 API Configuration
1. Open `backend.py`
2. Verify the FastAPI configuration:
```python
app = FastAPI(title="RRR Release Analysis Tool")
```

### 3.2 Cache Configuration
- Default cache TTL: 3 days
- Cache location: `cache.db` in project root
- To modify cache settings, edit `CACHE_TTL_SECONDS` in `backend.py`

## 4. Basic Usage

### 4.1 Starting the Application
```bash
python backend.py
```
The server will start at `http://127.0.0.1:8080`

### 4.2 Making Analysis Requests
1. Prepare your PDF files in a folder
2. Use the `/analyze` endpoint:
```python
import requests

response = requests.post(
    "http://127.0.0.1:8080/analyze",
    json={"folder_path": "/path/to/your/pdfs"}
)
```

### 4.3 Understanding the Response
The API returns:
- Metrics data
- Visualizations (base64 encoded)
- Analysis report
- Quality evaluation
- Extracted hyperlinks

## 5. Advanced Features

### 5.1 Custom Analysis
1. Modify metric thresholds in `backend.py`
2. Adjust visualization parameters
3. Customize report templates

### 5.2 Caching Management
- Clear cache: Delete `cache.db`
- Monitor cache size
- Adjust TTL as needed

### 5.3 Performance Optimization
- Adjust thread pool size
- Configure batch processing
- Optimize memory usage

## 6. Troubleshooting

### 6.1 Common Issues
1. **API Connection Errors**
   - Verify API credentials
   - Check network connection
   - Validate endpoint URL

2. **PDF Processing Errors**
   - Ensure PDFs are not corrupted
   - Check file permissions
   - Verify PDF format

3. **Memory Issues**
   - Reduce batch size
   - Clear cache
   - Monitor system resources

### 6.2 Debugging
1. Enable debug logging:
```python
logging.basicConfig(level=logging.DEBUG)
```

2. Check log files:
- `visualization.log`
- Application logs

### 6.3 Getting Help
- Check error messages
- Review documentation
- Contact support

## 7. Best Practices

### 7.1 PDF Preparation
- Use consistent naming conventions
- Ensure PDFs are readable
- Include all required sections

### 7.2 Performance
- Process PDFs in batches
- Regular cache cleanup
- Monitor system resources

### 7.3 Security
- Secure API credentials
- Regular updates
- Access control

## 8. Maintenance

### 8.1 Regular Tasks
- Clear old cache entries
- Update dependencies
- Backup data

### 8.2 Monitoring
- Check log files
- Monitor API usage
- Track performance

### 8.3 Updates
- Regular dependency updates
- Security patches
- Feature updates 