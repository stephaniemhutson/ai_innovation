import pandas as pd
import json


INPUT_CSV = './data/patent_data_03_01_2026.csv'
# Truncate text to stay under token limits (approx 4 chars = 1 token)
TRUNCATE_CHARS = 2000 # about 400 words. Abstract is going to have the richest information anyway.



SYSTEM_INSTRUCTION = """
SYSTEM INSTRUCTIONS:
You are an expert Patent Analyst seeking to understand AI patents which innovate at the fronteir. You are not interested in applications of AI. What does the patent innovate on? Given the instructions below, follow the procedure to create the

Options: [Chips, Servers, Data Center Infrastructure, Inference, Training, Other, Unrelated, Insufficient Data]

Note: Data Center Infrastructure includes cooling technologies used in data centers, energy management, and other relevant technologies.
Note: If there is not enough information for you to confidently categorize, label as Insufficient Data and do not continue to analyze.
Note: "Other" should be used for innovations that are related to the AI frontier, but are not part of the other categories. "Unrelated" is for innovations which are not on the AI frontier.
After determining the patent category, if the category is not "Unrelated" or "Insufficient Data", rate the patent on how much it innovates along a vector of energy efficiency, compute, algorithm and memory.
Energy efficiency reduces power needed to train a model, includes energy improvements in data center infrastructure such as cooling (eg. FLOPS/W go down)
Compute efficiency increases the speed at which computation may occur. (eg. FLOPS go up)
Algorithm efficiency decreases number of FLOPs needed for same computation (eg. Num FLOPs go down)
Memory increases that capacity to store information (eg. Max parameters go up)
Use the full range of the scale. Patents should score 0 for vectors they do not impact.
Only assign a 7+ for clearly superior technical advancements. Secondary impacts should be scored 4 or lower.

SCORING LOGIC:
Score 0-10.
0: No contribution.
5: Incremental improvement (e.g., standard cooling tweak).
10: Breakthrough (e.g., new transformer architecture, sub-nanometer chip process).

USER PROMPT:
Analyze the following patent data:
{application_number, title, cpcs, abstract, summary, background}

OUTPUT:
{
    "app_num": "",
    "category": "",
    "confidence": 0, # range from 0-1
    "reasoning": "Brief 1-sentence explanation",
    "energy": 0,
    "compute": 0,
    "algorithm": 0,
    "memory": 0
}
"""

PROCEDURE = """
### Reasoning Framework

1.  **Category Filtration (The Frontier Test):**
    *   The first step is to determine if the patent is **Core** or **Applied**.
    *   **Analyze CPCs & Title:** I look for hardware codes (H01L for semiconductors, H05K for circuits, F28D for cooling) vs. software codes (G06N for ML models). If the CPCs relate to consumer goods, agriculture, or finance, it is likely an **Application** and thus "Unrelated."
    *   **Infrastructure vs. Architecture:**
        *   **Chips:** Focus on logic, memory, packaging (CoWoS, HBM), and interconnects.
        *   **Data Center Infrastructure:** Focus on power delivery (GaN/SiC), liquid cooling, immersion cooling, and rack-scale architecture.
        *   **Training/Inference:** Focus on mathematical optimizations (quantization, pruning, attention mechanisms) or systems software (schedulers, compilers).

2.  **Scoring Vectors (Impact Analysis):**
    *   **Energy:** Does this innovation fundamentally lower Joules/Op? (e.g., Analog computing, 3D stacking shortening wire lengths, efficient cooling reducing PUE).
    *   **Compute:** Does this increase throughput or reduce latency? (e.g., Systolic arrays, optical interconnects, dedicated matrix multiplication units).
    *   **Algorithm:** Does this reduce the complexity of the math itself? (e.g., $O(n^2)$ to $O(n)$ complexity, sparse matrix operations).
    *   **Memory:** Does this increase bandwidth or capacity near the logic? (e.g., High Bandwidth Memory, in-memory compute).

3.  **Confidence Assessment:**
    *   High Confidence (>0.8): Clear abstract, specific technical keywords (e.g., "Through-Silicon Via," "Gradient Descent," "Two-Phase Immersion"), and alignment between Title and CPCs.
    *   Low Confidence (<0.5): Vague legal jargon, broad claims ("A system for processing data"), or missing summary/background fields.

---

### 3 New Examples

#### Example 1: Hardware/Chip Innovation (High Frontier Relevance)
**Input:**
```json
{
"application_number": "123",
"title": "Vertical Bitline 3D-NAND Architecture for In-Memory Matrix Multiplication",
"cpcs": ["G11C16/04", "G06N3/063", "H10B43/27"],
"abstract": "A non-volatile memory device configured to perform analog vector-matrix multiplication. The device comprises a three-dimensional array of memory cells, wherein bitlines are arranged vertically. A controller is configured to apply voltage pulses to wordlines representing input vector values, wherein the current accumulated on the bitlines represents the result of the matrix multiplication.",
"summary": "By utilizing the physical conductance of the memory cells to perform computation, the Von Neumann bottleneck is bypassed.",
"background": "Traditional AI accelerators suffer from high latency and energy consumption due to data transfer between DRAM and the GPU cores."
}
```

**Output:**
```json
{
"app_num": "123",
"category": "Chips",
"reasoning": "The patent describes a Compute-in-Memory (CIM) architecture using 3D-NAND, which directly addresses the Von Neumann bottleneck, a critical barrier in AI hardware.",
"confidence": 0.85,
"energy": 9,
"compute": 8,
"algorithm": 0,
"memory": 7
}
```

#### Example 2: Weak Energy Improvement
**Input:**
```json
{
"application_number": "456",
"title": "Rack-Mountable Blanking Panel with Cable Pass-Through Brush Seal",
"cpcs": ["H05K7/1488", "H05K7/20736"],
"abstract": "A blanking panel assembly for a standardized server rack. The panel covers unused rack units (U) to separate cold aisles from hot aisles. The assembly comprises a rigid frame and a flexible brush seal aperture that allows cables to pass from the front to the rear of the rack while inhibiting the backflow of exhaust air. The frame further includes tool-less snap-fit connectors for rapid installation.",
"summary": "By sealing unused rack space while accommodating cabling, the invention prevents the recirculation of hot air into the cold aisle, improving the overall cooling efficiency of the data center row.",
"background": "In data centers, open spaces in server racks can lead to the mixing of hot and cold air, causing cooling units to work harder to maintain target temperatures."
}
```

**Output:**
```json
{
"app_num": "456",
"category": "Data Center Infrastructure",
"reasoning": "The patent addresses airflow management (cooling) within data center racks, but the innovation is a standard mechanical blanking panel that offers only incremental improvements to energy efficiency.",
"confidence": 0.95,
"energy": 3,
"compute": 0,
"algorithm": 0,
"memory": 0
}
```

#### Example 3: Application of AI (Unrelated to Frontier)
**Input:**
```json
{
"application_number": "543",
"title": "System for Predictive Maintenance of HVAC Units Using Machine Learning",
"cpcs": ["F24F11/30", "G05B23/02"],
"abstract": "A system for monitoring an HVAC unit comprising a plurality of sensors configured to detect vibration and temperature. A processor receives sensor data and utilizes a trained neural network to predict component failure probability. When the probability exceeds a threshold, a maintenance alert is transmitted to a user device.",
"summary": "The system improves the longevity of residential air conditioning units.",
"background": "HVAC failures often occur unexpectedly, leading to user discomfort and high repair costs."
}
```

**Output:**
```json
{
"app_num": "543",
"category": "Unrelated",
"reasoning": "While this patent uses AI/ML, it is an application of existing technology to a specific vertical (HVAC maintenance) and does not improve the underlying capabilities of AI hardware or software.",
"confidence": 0.95,
"energy": 0,
"compute": 0,
"algorithm": 0,
"memory": 0
}
```
"""

def create_prompt(row):
    # Truncate long fields to save money/tokens
    summary = str(row.get('summary', ''))[:TRUNCATE_CHARS]
    background = str(row.get('background', ''))[:TRUNCATE_CHARS]

    user_content = (
        f"app_num: {row['application_number']}\n"
        f"title: {row['invention_title']}\n"
        f"abstract: {row['abstract']}\n"
        f"cpcs: {row['cpcs_list']}\n"
        f"summary: {summary}\n"
        f"background: {background}\n"
    )
    return user_content

def convert_csv_to_jsonl(csv_path, system_instruction, model):
    df = pd.read_csv(csv_path)
    df = df.sample(frac=1, random_state=42)

    generation_config = {
        "response_mime_type": "application/json",
        "temperature": 0.1, # Low temperature for consistency
        # "thinking_level": "minimal",
        # "max_output_tokens": 200,
        "response_schema": {
            'required': [
                'app_num',
                'category',
                'reasoning',
                'confidence',
                'memory',
                'energy',
                'compute',
                'algorithm'
            ],
            'properties': {
                'app_num': {'type': 'STRING'},
                'category': {'type': 'STRING'},
                'reasoning': {'type': 'STRING'},
                'confidence': {'type': 'NUMBER'},
                'memory': {'type': 'STRING'},
                'energy': {'type': 'STRING'},
                'compute': {'type': 'STRING'},
                'algorithm': {'type': 'STRING'},
            },
            'type': 'OBJECT'
        }
    }

    if model == 2.5:
        generation_config["thinking_config"] = {"thinking_budget": 1200}
    elif model == 3:
        generation_config["thinking_level"] = "minimal"

    for i in range(10):
        jsonl_path = f"./data/inputs/batches_model{model}_{i*50000}_{(i+1)*50000}.jsonl"

        sub_df = df[i*50000: (i+1)*50000]
        if len(sub_df) > 0:
            with open(jsonl_path, 'w', encoding='utf-8') as f:
                # for _, row in df.iterrows():
                # Gemini Batch API structure
                requests = [{
                    "key": row['application_number'],
                    "request": {
                        "contents": [
                            {
                                "parts": [{"text": create_prompt(row)}],
                                "role": "user"
                            },
                            {
                                "parts": [{"text": PROCEDURE}],
                                "role": "model"

                            }
                        ],
                        "system_instruction": {
                            "parts": [{"text": system_instruction}]
                        },
                        "generation_config": generation_config
                    }
                } for _, row in sub_df.iterrows() ]
                for request in requests:
                    f.write(json.dumps(request) + "\n")


if __name__ == "__main__":
    model = float(input("Which model? 2.5 or 3? "))
    convert_csv_to_jsonl(INPUT_CSV, SYSTEM_INSTRUCTION, model)
