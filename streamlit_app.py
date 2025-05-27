import os
import re
import json
import runpy
import subprocess
from typing import List, Dict, Tuple
from collections import defaultdict
from dotenv import load_dotenv
from PyPDF2 import PdfReader
from crewai import Agent, Task, Crew, Process, LLM
from langchain_openai import AzureChatOpenAI
import streamlit as st
import ssl
import warnings
import shutil
warnings.filterwarnings("ignore")

# Disable SSL verification
ssl._create_default_https_context = ssl._create_unverified_context

# Load environment variables
load_dotenv()

# Initialize Azure OpenAI
llm = LLM(
    model=f"azure/{os.getenv('DEPLOYMENT_NAME')}",
    api_version=os.getenv("AZURE_API_VERSION"),
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    base_url=os.getenv("AZURE_OPENAI_ENDPOINT"),
    temperature=0.1,
    top_p=0.9,
)

# Constants
START_HEADER_PATTERN = 'Release Readiness Critical Metrics (Previous/Current):'
END_HEADER_PATTERN = 'Release Readiness Functional teams Deliverables Checklist:'

def get_pdf_files_from_folder(folder_path: str) -> List[str]:
    pdf_files = []
    if not os.path.exists(folder_path):
        raise FileNotFoundError(f"The folder {folder_path} does not exist.")
   
    for file_name in os.listdir(folder_path):
        if file_name.lower().endswith('.pdf'):
            full_path = os.path.join(folder_path, file_name)
            pdf_files.append(full_path)
   
    if not pdf_files:
        raise FileNotFoundError(f"No PDF files found in the folder {folder_path}.")
   
    return pdf_files

def extract_text_from_pdf(pdf_path: str) -> str:
    with open(pdf_path, 'rb') as file:
        reader = PdfReader(file)
        text = ''
        for page in reader.pages:
            text += page.extract_text()
    return text

def extract_hyperlinks_from_pdf(pdf_path: str) -> List[Dict[str, str]]:
    """Extract all hyperlinks from a PDF file"""
    hyperlinks = []
    with open(pdf_path, 'rb') as file:
        reader = PdfReader(file)
       
        for page_num, page in enumerate(reader.pages, start=1):
            if '/Annots' in page:
                for annot in page['/Annots']:
                    annot_obj = annot.get_object()
                    if annot_obj['/Subtype'] == '/Link' and '/A' in annot_obj:
                        uri = annot_obj['/A']['/URI']
                        text = page.extract_text()
                        context_start = max(0, text.find(uri) - 50)
                        context_end = min(len(text), text.find(uri) + len(uri) + 50)
                        context = text[context_start:context_end].strip()
                       
                        hyperlinks.append({
                            "url": uri,
                            "context": context,
                            "page": page_num,
                            "source_file": os.path.basename(pdf_path)
                        })
    return hyperlinks

def locate_table(text: str, start_header: str, end_header: str) -> str:
    start_index = text.find(start_header)
    end_index = text.find(end_header)
    if start_index == -1:
        raise ValueError(f'Header {start_header} not found in text')
    if end_index == -1:
        raise ValueError(f'Header {end_header} not found in text')
    return text[start_index:end_index].strip()

def evaluate_with_llm_judge(source_text: str, generated_report: str) -> Tuple[int, str]:
    """Use LLM as an independent judge to evaluate report accuracy"""
    judge_llm = AzureChatOpenAI(
        api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        api_version=os.getenv("AZURE_API_VERSION"),
        azure_deployment=os.getenv("DEPLOYMENT_NAME"),
        temperature=0,
        max_tokens=512,
        timeout=None,
    )
   
    prompt = f"""Act as an impartial judge evaluating report quality. You will be given:
1. ORIGINAL SOURCE TEXT (extracted from PDF)
2. GENERATED REPORT (created by AI)

Evaluate based on:
- Data accuracy (50% weight): Does the report correctly reflect the source data?
- Analysis depth (30% weight): Does it provide meaningful insights?
- Clarity (20% weight): Is the presentation clear and professional?

ORIGINAL SOURCE:
{source_text}

GENERATED REPORT:
{generated_report}

INSTRUCTIONS:
1. Provide a score from 0-100
2. Give brief 2-3 sentence evaluation
3. Use EXACTLY this format:
Score: [0-100]
Evaluation: [your evaluation]

Your evaluation:"""
   
    response = judge_llm.invoke(prompt)
    response_text = response.content
   
    # Extract score and evaluation
    try:
        score_line = next(line for line in response_text.split('\n') if line.startswith('Score:'))
        score = int(score_line.split(':')[1].strip())
        eval_lines = [line for line in response_text.split('\n') if line.startswith('Evaluation:')]
        evaluation = ' '.join(line.split('Evaluation:')[1].strip() for line in eval_lines)
        return score, evaluation
    except Exception as e:
        print(f"Error parsing judge response: {e}\nResponse was:\n{response_text}")
        return 50, "Could not parse evaluation"

def setup_crew(extracted_text: str) -> Crew:
    """Configure and return the Crew with all tasks"""
   
    # Agent 1: Data Structurer
    structurer = Agent(
        role="Data Architect",
        goal="Structure raw release data into VALID JSON format",
        backstory="Expert in transforming unstructured data into clean JSON structures",
        llm=llm,
        verbose=True,
        memory=True,
    )

    structure_task = Task(
        description=f"""Convert this release data to STRICT JSON:
        {extracted_text}
       
        RULES:
        1. Output MUST be valid JSON only
        2. Use this EXACT structure:
        {{
            "metrics": {{
                "category": {{
                    "subcategory": [
                        {{"version": "x.y", "value": N, "status": "TEXT"}}
                    ]
                }}
            }}
        }}
        3. No text outside the JSON
        4. Use double quotes only""",
        agent=structurer,
        expected_output="Valid JSON string with no extra text"
    )

    # Agent 2: Trend Analyst
    analyst = Agent(
        role="Trend Analyst",
        goal="Add trends to metrics data and maintain valid JSON",
        backstory="Data scientist specializing in metric analysis",
        llm=llm,
        verbose=True,
        memory=True,
    )

    analysis_task = Task(
        description="""Enhance metrics JSON with trends:
        1. Input is JSON from Data Structurer
        2. Add 'trend' field to each metric
        3. Output MUST be valid JSON
        4. Format trends as: "↑ (X%)", "↓ (Y%)", or "→"
       
        Example output:
        {{
            "metrics": {{
                "defects": {{
                    "ATLS": [
                        {{"version": "25.1", "value": 42, "status": "MEDIUM RISK", "trend": "↓ (50%)"}}
                    ]
                }}
            }}
        }}""",
        agent=analyst,
        context=[structure_task],
        expected_output="Valid JSON string with trend analysis"
    )

    # Agent 3: Data Visualizer
    visualizer = Agent(
        role="Data Visualizer",
        goal="Generate visualization Python script",
        backstory="Expert in creating technical visualizations",
        llm=llm,
        verbose=True,
        memory=True,
    )

    visualization_task = Task(
        description="""Create a Python script that:
        1. Takes 'metrics' JSON variable as input
        2. Generates 3+ professional charts each with:
           - `plt.figure(figsize=(8,5),dpi=120)`
        3. Saves plots to 'visualizations/' as PNG
        4. Script must run independently
       
        OUTPUT REQUIREMENTS:
        - ONLY the Python code
        - NO markdown formatting
        - MUST use this exact directory: 'visualizations/'
        - MUST include error handling"""
        ,
        agent=visualizer,
        context=[analysis_task],
        expected_output="Complete Python script as plain text"
    )

    # Agent 4: Report Generator
    reporter = Agent(
        role="Technical Writer",
        goal="Generate markdown report",
        backstory="Technical writer for software metrics",
        llm=llm,
        verbose=True,
        memory=True,
    )

    report_task = Task(
        description="""Create markdown report:
        1. Use tables with trends
        2. Highlight statuses
        3. Format with:
        | Release | Metric | Status | Trend |
        |---------|--------|--------|-------|
        | 25.1    | 42     | MEDIUM RISK | ↓ (50%) |
       
        Include:
        - Key findings
        - Recommendations""",
        agent=reporter,
        context=[analysis_task],
        expected_output="Markdown report with tables and analysis"
    )

    return Crew(
        agents=[structurer, analyst, visualizer, reporter],
        tasks=[structure_task, analysis_task, visualization_task, report_task],
        process=Process.sequential,
        verbose=True
    )

def clean_json_output(raw_output: str) -> dict:
    """Extract JSON from agent output with robust error handling"""
    try:
        # Try direct parse first
        return json.loads(raw_output)
    except json.JSONDecodeError:
        try:
            # Extract JSON from between ``` markers
            cleaned = re.search(r'```json\n({.*?})\n```', raw_output, re.DOTALL)
            if cleaned:
                return json.loads(cleaned.group(1))
           
            # Try extracting first JSON-like block
            cleaned = re.search(r'\{.*\}', raw_output, re.DOTALL)
            if cleaned:
                return json.loads(cleaned.group(0))
               
            raise ValueError("No valid JSON found in output")
        except Exception as e:
            st.error(f"Failed to parse JSON: {e}\nRaw output:\n{raw_output}")
            raise

def apply_custom_styles():
    st.markdown("""
    <style>
        /* Table styling */
        table {
            width: 100%;
            border-collapse: collapse;
            margin: 1rem 0;
            font-family: Arial, sans-serif;
        }
        th {
            background-color: #2a3f5f;
            color: white;
            padding: 10px;
            text-align: left;
        }
        td {
            padding: 8px 10px;
            border-bottom: 1px solid #ddd;
        }
        tr:nth-child(even) { background-color: #f9f9f9; }
       
        /* Trend arrows */
        .trend-up { color: #2ecc71; font-weight: bold; }
        .trend-down { color: #e74c3c; font-weight: bold; }
        .trend-neutral { color: #3498db; font-weight: bold; }
       
        /* Risk levels */
        .risk-high { color: #e74c3c; font-weight: bold; }
        .risk-medium { color: #f39c12; font-weight: bold; }
        .risk-low { color: #2ecc71; font-weight: bold; }
       
        /* Report text */
        .report-text { line-height: 1.6; }
        .report-section { margin-bottom: 1.5rem; }
       
        /* Evaluation section */
        .evaluation-card {
            background-color: #f8f9fa;
            border-radius: 8px;
            padding: 20px;
            margin: 20px 0;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .score-display {
            font-size: 24px;
            font-weight: bold;
            margin: 10px 0;
        }
       
        /* Hyperlinks section */
        .hyperlink-card {
            background-color: #f0f7ff;
            border-radius: 8px;
            padding: 15px;
            margin: 15px 0;
            border-left: 4px solid #2a3f5f;
        }
        .hyperlink-item {
            margin-bottom: 10px;
            padding-bottom: 10px;
            border-bottom: 1px solid #e0e0e0;
        }
        .hyperlink-url {
            font-weight: bold;
            color: #2a3f5f;
        }
        .hyperlink-context {
            color: #666;
            font-size: 0.9em;
        }
        .hyperlink-source {
            font-size: 0.8em;
            color: #999;
        }
    </style>
    """, unsafe_allow_html=True)

def enhance_report_markdown(md_text):
    # Remove any residual code fences if present
    cleaned = re.sub(r'^```markdown\n|\n```$', '', md_text, flags=re.MULTILINE)
   
    # Enhance tables and special formatting
    enhanced = cleaned.replace("MEDIUM RISK", "<span class='risk-medium'>MEDIUM RISK</span>") \
                     .replace("HIGH RISK", "<span class='risk-high'>HIGH RISK</span>") \
                     .replace("LOW RISK", "<span class='risk-low'>LOW RISK</span>") \
                     .replace("ON TRACK", "<span class='risk-low'>ON TRACK</span>")
   
    # Enhance trend arrows
    enhanced = re.sub(r'(↑ \([^)]+\))', r'<span class="trend-up">\1</span>', enhanced)
    enhanced = re.sub(r'(↓ \([^)]+\))', r'<span class="trend-down">\1</span>', enhanced)
    enhanced = re.sub(r'(→)', r'<span class="trend-neutral">\1</span>', enhanced)
    enhanced = enhanced.rstrip().removesuffix('</div>')
    return enhanced

def display_hyperlinks(hyperlinks):
    """Display extracted hyperlinks in a formatted way"""
    if not hyperlinks:
        st.info("No hyperlinks found in the PDF files.")
        return
   
    st.markdown("## Extracted Hyperlinks")
    st.markdown("The following hyperlinks were found in the PDF documents:")
   
    for link in hyperlinks:
        st.markdown(f"""
        <div class="hyperlink-card">
            <div class="hyperlink-item">
                <div><a href="{link['url']}" target="_blank" class="hyperlink-url">{link['url']}</a></div>
                <div class="hyperlink-context">Context: {link['context']}</div>
                <div class="hyperlink-source">
                    Source: {link['source_file']} (Page {link['page']})
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

def main():
    st.set_page_config(page_title="RRR Analysis Tool", layout="wide")
    apply_custom_styles()

    st.image("Zebra_Logo_K-300x120.jpg", width=200)
    st.title("RRR CONFLUENCE ANALYSIS TOOL")

    # File input
    data_folder = st.sidebar.text_input("PDF Folder Path", placeholder="Enter folder path")
   
    if st.button("Analyze PDFs"):
        if not data_folder:
            st.warning("Please enter a folder path")
            return
           
        with st.spinner("Processing..."):
            try:
                # Step 1: Extract PDF text and hyperlinks
                pdf_files = get_pdf_files_from_folder(data_folder)
                extracted_texts = [
                    locate_table(extract_text_from_pdf(pdf), START_HEADER_PATTERN, END_HEADER_PATTERN)
                    for pdf in pdf_files
                ]
                full_source_text = "\n".join(
                    f"File: {os.path.basename(pdf)}\n{text}"
                    for pdf, text in zip(pdf_files, extracted_texts))
               
                # Extract all hyperlinks from all PDFs
                all_hyperlinks = []
                for pdf in pdf_files:
                    all_hyperlinks.extend(extract_hyperlinks_from_pdf(pdf))
               
                # Step 2: Setup crew and run analysis
                crew = setup_crew(full_source_text)
                crew_result = crew.kickoff()
               
                # Get references to tasks
                analysis_task = crew.tasks[1]
                visualization_task = crew.tasks[2]
                report_task = crew.tasks[3]
               
                # Step 3: Process metrics with robust JSON handling
                try:
                    metrics = clean_json_output(analysis_task.output.raw)
                except Exception as e:
                    st.error(f"Metrics parsing failed: {e}")
                    return
               
                # Step 4: Generate visualizations
                script_path = "visualizations.py"
                folder_path = "visualizations"
                raw_script = visualization_task.output.raw
                clean_script = re.sub(r'```python|```$', '', raw_script, flags=re.MULTILINE).strip()

                with open(script_path, "w", encoding="utf-8") as f:
                    f.write(clean_script)
                if os.path.exists(folder_path):
                   shutil.rmtree(folder_path)
                os.makedirs(folder_path, exist_ok=True)
               
                try:
                    # Try runpy first
                    runpy.run_path(script_path, init_globals={'metrics': metrics})
                except Exception as e:
                    st.warning(f"Runpy failed, trying subprocess: {e}")
                    subprocess.run(["python", script_path], check=True)
               
                # Display visualizations
                st.markdown("## Visualizations")
                viz_dir = "visualizations"
                if os.path.exists(viz_dir):
                    for img in sorted(f for f in os.listdir(viz_dir) if f.endswith('.png')):

                        st.image(os.path.join(viz_dir, img),width=600)
                else:
                    st.warning("No visualizations generated")

                # Display enhanced report
                st.markdown("## Analysis Report")
                enhanced_report = enhance_report_markdown(report_task.output.raw)
                st.markdown(f"""
                <div class="report-text">
                    {enhanced_report}
                </div>
                """, unsafe_allow_html=True)

                # LLM-as-Judge Evaluation
                with st.spinner("Evaluating report quality..."):
                    score, evaluation = evaluate_with_llm_judge(
                        full_source_text,
                        report_task.output.raw
                    )

                    st.markdown("## Report Quality Evaluation")
                    st.markdown(f"""
                    <div class="evaluation-card">
                        <h3>LLM Judge Assessment</h3>
                        <div class="score-display" style="color: {'#2ecc71' if score > 75 else '#f39c12' if score > 50 else '#e74c3c'}">
                            Score: {score}/100
                        </div>
                        <div class="evaluation-text">
                            <strong>Evaluation:</strong> {evaluation}
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
               
                # Display extracted hyperlinks
                display_hyperlinks(all_hyperlinks)

            except Exception as e:
                st.error(f"Analysis failed: {str(e)}")



if __name__ == "__main__":
    main()
