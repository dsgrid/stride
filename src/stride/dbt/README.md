This is stride's internal dbt project.

### Using the project

Stride builds the dbt project at runtime with a command in the following format:
```
$ dbt run --vars '{"scenario": "baseline", "country": "country_1", "model_years": "(2025,2030,2035,2040,2045)"}'
```

When debugging problems it can be used to inspect the actual SQL queries used in
`<your-project-path>/dbt/target/compiled/stride/models/`.

### Resources:
- Learn more about dbt [in the docs](https://docs.getdbt.com/docs/introduction)
- Check out [Discourse](https://discourse.getdbt.com/) for commonly asked questions and answers
- Join the [chat](https://community.getdbt.com/) on Slack for live discussions and support
- Find [dbt events](https://events.getdbt.com) near you
- Check out [the blog](https://blog.getdbt.com/) for the latest news on dbt's development and best practices
