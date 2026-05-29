from backend.src.services.llm_query import LLMQuery

def test_init_success():
    llm = LLMQuery("test_task")
    assert llm.task_name == "test_task"

def test_reset_metadata_highlights(project_factory):
    llm = LLMQuery("extract_highlights")
    llm.reset_metadata(project_factory)
    assert project_factory.highlights == []

def test_reset_metadata_other(project_factory):
    llm = LLMQuery("other_task")
    llm.reset_metadata(project_factory)
    # The fixture already initializes the object, verify it wasn't modified in an unexpected way
    assert project_factory.highlights is not None

def test_start_service(project_factory):
    llm = LLMQuery("extract_highlights")
    llm.start_service(project_factory)
    assert project_factory.highlights == []

def test_end_service(project_factory):
    llm = LLMQuery("any")
    llm.end_service(project_factory)
