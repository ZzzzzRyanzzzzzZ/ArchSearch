from flask import Flask, request, jsonify
from flask_cors import CORS
from openai import OpenAI
import httpx
import pymupdf as fitz
import json
import re

app = Flask(__name__)
CORS(app)

API_KEY = "rc_5ebd1e7ad19198080c3677ebfd7c5fe8af6fafdffdf50b2e2e4d01edcea5a23a"
MODEL = "Qwen/Qwen2.5-7B-Instruct"

client = OpenAI(
    base_url="https://api.featherless.ai/v1",
    api_key=API_KEY,
)

# Persistent storage object
PDF_STORAGE = {
    "text": "",
    "filename": ""
}


def extract_json_block(raw_text):
    """
    Models often wrap JSON in ```json ... ``` fences, add a leading
    sentence, or add trailing commentary. This pulls out the first
    {...} block and parses it, rather than assuming the response is
    pure JSON.
    """
    if not raw_text:
        raise ValueError("Empty response from model")

    # Strip markdown code fences if present
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw_text, re.DOTALL)
    if fenced:
        candidate = fenced.group(1)
    else:
        # Fall back to grabbing the first {...} span in the text
        brace_match = re.search(r"\{.*\}", raw_text, re.DOTALL)
        if not brace_match:
            raise ValueError("No JSON object found in model response")
        candidate = brace_match.group(0)

    return json.loads(candidate)


@app.route("/api/paperfinder", methods=["POST"])
def api_paperfinder():
    data = request.get_json()
    prompt = data.get("topic", "")

    try:
        response = client.chat.completions.create(
            model=MODEL,
            max_tokens=30,
            messages=[
                {"role": "system", "content": "Convert topic to 2-4 academic search terms. Respond with ONLY search terms, max 8 words."},
                {"role": "user", "content": prompt}
            ]
        )
        searchterms = response.choices[0].message.content.strip()

        alex_api_key = "WlD85XJbzQmP83sj01Ebl6"
        response3 = httpx.get("https://api.openalex.org/works", params={"search": searchterms, "per_page": 5, "api_key": alex_api_key})
        alex_data = response3.json()

        paper_records = []
        for i in alex_data.get("results", []):
            title = i.get('title', 'Untitled')
            url = i.get('doi') or (i.get('primary_location', {}) or {}).get('landing_page_url') or "https://openalex.org"
            authorships = i.get("authorships", [])
            names = [a["author"]["display_name"] for a in authorships if "author" in a and "display_name" in a["author"]]

            paper_records.append({
                "paper_title": title,
                "paper_url": url,
                "professor_name": ", ".join(names[:2]) if names else "Unknown Author"
            })

        return jsonify({"searchterms": searchterms, "results": paper_records})

    except Exception as e:
        return jsonify({
            "searchterms": prompt,
            "results": [{"paper_title": f"Study on {prompt}", "paper_url": "https://openalex.org", "professor_name": "Dr. Research Lead"}],
            "error": str(e)
        }), 200


@app.route("/api/upload_pdf", methods=["POST"])
def upload_pdf():
    if 'file' not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "Empty filename"}), 400

    try:
        doc = fitz.open(stream=file.read(), filetype="pdf")
        extracted_text = ""
        for i, page in enumerate(doc):
            extracted_text += f"\n--- Page {i+1} ---\n" + page.get_text()

        # Save to persistent storage structure
        PDF_STORAGE["text"] = extracted_text
        PDF_STORAGE["filename"] = file.filename

        # Summary generation with optimized tokens
        response = client.chat.completions.create(
            model=MODEL,
            max_tokens=250,
            messages=[
                {"role": "system", "content": "Provide a brief, bulleted summary of the core thesis and methodology."},
                {"role": "user", "content": f"Document Text:\n{extracted_text[:3000]}"}
            ],
            temperature=0.3
        )
        summary = response.choices[0].message.content.strip()

        # Opening debate question
        intro_response = client.chat.completions.create(
            model=MODEL,
            max_tokens=80,
            messages=[
                {"role": "system", "content": "Ask a sharp, single Socratic question testing the user on this summary. Keep it brief."},
                {"role": "user", "content": f"Summary:\n{summary}"}
            ],
            temperature=0.4
        )
        opening_question = intro_response.choices[0].message.content.strip()

        # --- Simulation generation ---
        # Fallback used ONLY if the model call fails or returns unparsable JSON
        fallback_sim_data = {
            "description": f"Custom agent-based or mathematical model tracking dynamics extracted from {file.filename}.",
            "code": "import numpy as np\nimport matplotlib.pyplot as plt\n\ndef run_pdf_simulation():\n    t = np.linspace(0, 50, 100)\n    y = np.exp(-0.1 * t) * np.cos(t)\n    plt.plot(t, y)\n    plt.title('Extracted PDF Simulation Dynamics')\n    plt.show()\n\nrun_pdf_simulation()",
            "sources": f"Extracted directly from uploaded document: {file.filename}"
        }

        sim_data = fallback_sim_data
        sim_error = None

        try:
            sim_response = client.chat.completions.create(
                model=MODEL,
                max_tokens=500,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You analyze a research paper and design a runnable Python simulation "
                            "that models the core dynamics/process described in it. "
                            "Respond with ONLY a raw JSON object (no markdown fences, no commentary) "
                            "with exactly these keys:\n"
                            '  "description": a 1-3 sentence explanation of what the simulation models and why it reflects the paper,\n'
                            '  "code": a complete, runnable Python script using numpy and matplotlib that implements the simulation, '
                            'with realistic parameter values inferred from the paper where possible,\n'
                            '  "sources": a short string naming which parameters/assumptions came from the paper text.\n'
                            "Escape newlines inside the code string as \\n so the JSON stays valid."
                        )
                    },
                    {"role": "user", "content": f"Document Text:\n{extracted_text[:3000]}"}
                ],
                temperature=0.3
            )
            sim_raw = sim_response.choices[0].message.content.strip()
            parsed = extract_json_block(sim_raw)

            # Validate required keys are present and non-empty before trusting it
            if all(parsed.get(k) for k in ("description", "code", "sources")):
                sim_data = {
                    "description": parsed["description"],
                    "code": parsed["code"],
                    "sources": parsed["sources"]
                }
            else:
                sim_error = "Model response missing required simulation fields; used fallback."

        except Exception as sim_exc:
            sim_error = f"Simulation generation failed, used fallback: {sim_exc}"

        result = {
            "message": "Processed successfully",
            "filename": file.filename,
            "summary": summary,
            "opening_question": opening_question,
            "simulation": sim_data
        }
        if sim_error:
            result["simulation_warning"] = sim_error

        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/pdfscanner", methods=["POST"])
def api_pdfscanner():
    data = request.get_json()
    question = data.get("question", "").strip().lower()

    try:
        text_to_use = PDF_STORAGE["text"]
        if not text_to_use:
            return jsonify({"answer": "No PDF context found. Please upload a PDF file first on the right panel."})

        is_stuck = any(word in question for word in ["idk", "i don't know", "dont know", "what", "help", "explain", "clue", "?"])

        if is_stuck:
            system_prompt = "The user is stuck or doesn't know the answer. Explain the answer or concept directly from the document context in 2 concise sentences."
        else:
            system_prompt = "You are a sharp academic debater. Challenge the user's thesis using the text context. If they are wrong or vague, correct them using the text. Keep responses under 3 sentences. Make sure you only generate one single opening question to start the debat,. Do not provide a list of multiple questions."

        response = client.chat.completions.create(
            model=MODEL,
            max_tokens=120,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Context Snippet:\n{text_to_use[:3000]}\n\nUser Input: {question}"}
            ],
            temperature=0.4
        )

        return jsonify({"answer": response.choices[0].message.content})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(port=5000, debug=True)
