# QuestionSet YAML must conform to gradeflow_engine.question_sets.model.QuestionSet:
# - Top-level key: question_map
# - Each entry: <QuestionId>: { type: <TEXT|NUMERIC|CHOICE|MULTI_VALUED>, ... }
QUESTION_SET_YAML: str = """
question_map:
  q1:
    type: TEXT
    description: "Your name?"
    max_points: 1.0
  q2:
    type: NUMERIC
    description: "Score?"
    max_points: 2.0
  q3:
    type: CHOICE
    description: "Select letter"
    max_points: 1.5
    options:
      - A
      - B
      - C
    allow_multiple: false
    config:
      delimiter: ","
      trim_whitespace: true
      normalize_case: false
  q4:
    type: MULTI_VALUED
    description: "Two-part answer"
    max_points: 2.0
    value_types:
      - TEXT
      - TEXT
    config:
      delimiter: "|"
      trim_whitespace: true
      normalize_case: false
"""

# Rubric YAML must conform to gradeflow_engine.rubrics.model.Rubric:
# - Top-level key: rules
# - Each rule is a discriminated union by "type"
#   Here we use:
#   - TEXT_MATCH for q1 (expects exact text "Alice")
#   - NUMERIC_RANGE for q2 (expects 0 <= score <= 100)
RUBRIC_YAML: str = """
rules:
  - type: TEXT_MATCH
    question_id: q1
    answers:
      - "Alice"
    max_points: 1.0
  - type: NUMERIC_RANGE
    question_id: q2
    min_value: 0
    max_value: 100
    max_points: 2.0
  - type: MULTIPLE_CHOICE
    question_id: q3
    answer:
      - A
    max_points: 1.5
  - type: MULTI_VALUED
    question_id: q4
    rules:
      - type: TEXT_MATCH
        question_id: q4_1
        answers:
          - "1"
      - type: TEXT_MATCH
        question_id: q4_2
        answers:
          - "a"
    aggregation: ALL
    max_points: 2.0
"""

# Submissions CSV must have a student_id column and columns for each question ID (q1, q2).
SUBMISSIONS_CSV: str = "student_id,q1,q2,q3,q4\ns1,Alice,90,A,1|a\ns2,Bob,76,B,2|b\n"
