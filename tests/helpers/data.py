# A stable assessment ID used across tests
ASSESSMENT_ID: str = "cs1-midterm"

# QuestionSet YAML must conform to gradeflow_engine.question_sets.model.QuestionSet:
# - Top-level key: question_map
# - Each entry: <QuestionId>: { type: <TEXT|NUMERIC|CHOICE|MULTI_VALUED>, ... }
QUESTION_SET_YAML: str = """
question_map:
  q1:
    type: TEXT
    description: "Your name?"
  q2:
    type: NUMERIC
    description: "Score?"
"""

# Rubric YAML must conform to gradeflow_engine.rubrics.model.Rubric:
# - Top-level key: rules
# - Each rule is a discriminated union by "type"
#   Here we use:
#   - EXACT_MATCH for q1 (expects exact text "Alice")
#   - NUMERIC_RANGE for q2 (expects 0 <= score <= 100)
RUBRIC_YAML: str = """
rules:
  - type: EXACT_MATCH
    question_id: q1
    answer: "Alice"
    max_points: 1.0
  - type: NUMERIC_RANGE
    question_id: q2
    min_value: 0
    max_value: 100
    max_points: 2.0
"""

# Submissions CSV must have a student_id column and columns for each question ID (q1, q2).
SUBMISSIONS_CSV: str = "student_id,q1,q2\ns1,Alice,90\ns2,Bob,76\n"
