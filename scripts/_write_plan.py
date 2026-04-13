import pathlib
content = open(pathlib.Path(__file__).parent / "_plan_content.md", encoding="utf-8").read()
with open("C:/Users/Admin/K-V3/docs/operations/evidence/phase_b_ohlcv_400d_ingestion_verification_plan.md", "w", encoding="utf-8") as f:
    f.write(content)
print("written", len(content), "chars")
