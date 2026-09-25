# Why Setowa

Team LEX chose the Cloudinary problem statement and narrowed it to cleanup evidence. The goal is not to compete with Cloudinary storage, transformations, or general search. Setowa adds project context, dated visit ordering, claim-level evidence, a human approval gate, and a report generated from saved decisions.

| Option | Decision | Reason |
| --- | --- | --- |
| Generic AI media dashboard | Deferred | Broad, hard to verify in a short demo. |
| Automatic impact score from photos | Rejected for MVP | Images alone cannot prove weight, area, causality, or long-term impact. |
| Reviewable before/after cleanup report | Chosen | Concrete workflow, inspectable evidence, and a clear human responsibility. |
| Video search / RAG / pair suggestions | Later only if needed | Useful references exist, but these do not replace the review-and-report core. |

The product test is simple: can a judge trace each sentence in the exported report to the approved text and the original before/after media? If not, the feature is not ready. See [LEX_Milestone.md](LEX_Milestone.md) for acceptance criteria and [ARCHITECTURE.md](ARCHITECTURE.md) for implementation.
