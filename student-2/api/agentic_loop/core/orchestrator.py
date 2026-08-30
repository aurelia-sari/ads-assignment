from agentic_loop.pipelines.recommendation_pipeline import run_recommendation


def run_agentic_recommendation(question):
    result = run_recommendation(question)

    if result["validation"]["valid"]:
        return result

    print("Observe failed. Adapt: retrying recommendation...")

    retry_question = (
        f"{question}\n\n"
        "Important: Recommend exactly one place from the supplied candidates. "
        "Do not invent or use any place outside the supplied data."
    )

    retry_result = run_recommendation(retry_question)

    return retry_result