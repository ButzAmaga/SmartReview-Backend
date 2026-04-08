# Tools to use
- sqlalchemy
- pydantic
- fastapi

# Generate the table

### Topics Table
- id
- name

QA_items
- id
- topic_id
- question
- answer


# Generate the route:
1. accepts list of question and topic name then save the list of questions to QA_items and topic name to topics table and connect them, return the topic name and number of question saved
