# ArchSearch
ArchSearch is an advanced academic research tool that can find papers and professors relevant to your topic. It breaks down complex research with summaries and questions to elevate your education. It also generate simulation code depending on what you upload in the pdf upload section. 

# FEATURES
- Paper & Professor Discovery - An agent create search terms based of your input and finds paper and professors using OpenAlex based off the terms that were created. OpenAlex is a database with thousands of research papers/professors. 
- Interactive Debate Agent - Based off the research paper you uploaded, this agent asks questions regarding the research paper, ensuring you have a better understanding of the paper uploaded.
- PDF Uploader and Smart Summary - This agent applies keywords to handle particular pages because of token limits, and it leverages those keywords to filter the PDF papers before generating a summary derived from the filtered papers.
- Simulation Studio - Creates computational models and python simulation code based on the literature that has been uploaded in the pdf uploader and the parameter bounds.
- Reliability & Confidence Scoring - It gives you an overall score on papers for their methodological rigor, automated checks, and auto-generated APA citations.

## To get started:
Clone/download repository.
In workflow.py, add your api key in "API_KEY"
Run your cmd in the folder of the scripts.
Type in your cmd python -m workflow.py to make sure the backend is running
Go to your frontend (index), and click on it.

