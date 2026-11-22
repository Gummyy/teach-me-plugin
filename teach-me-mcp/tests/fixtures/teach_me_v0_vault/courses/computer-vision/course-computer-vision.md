---
name: Computer vision
user: '[[user-alice]]'
status: active
subject: Computer vision with CNNs.
starting_level: Knows linear algebra.
created_at: 2026-11-22T01:08
updated_at: 2026-11-22T01:08
projects:
- '[[project-pet-classifier]]'
skills:
- '[[skill-convolution]]'
- '[[skill-cnn-architecture]]'
resources:
- slug: 3blue1brown-but-what-is-a-convolution
  title: 3Blue1Brown - But what is a convolution ?
  web_url: https://www.youtube.com/watch?v=KuXjwB4LzSA
  status: new
  created_at: 2026-11-22T01:08
  session: 2026-11-22 01:08
- slug: old-notes
  title: Old notes
  file_path: notes.pdf
  status: unprocessed
  created_at: 2026-11-22T01:08
  session: 2026-11-22 01:08
plan:
- slug: convolution
  kind: class
  title: Convolution
  description: Kernels and feature maps
  skills:
  - convolution
  importance: core
  resources:
  - 3Blue1Brown on convolutions
- slug: convolution-quiz
  kind: quiz
  title: Convolution quiz
  description: ''
  skills:
  - convolution
  importance: core
- slug: pooling
  kind: class
  title: Pooling
  description: Max pooling.
  skills: []
  importance: optional
  added: true
- slug: cnn-architectures
  kind: class
  title: CNN architectures
  description: ''
  skills:
  - cnn-architecture
  importance: optional
- slug: first-cnn
  kind: project
  title: First CNN
  description: Train a CNN on the pictures
  skills:
  - convolution
  - cnn-architecture
  importance: core
---

## Plan

| # | Step | Type | Description | Skills | Importance | Progress |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | [[class-convolution\|Convolution]] | 📖 class | Kernels and feature maps | convolution | core | ✅ done |
| 2 | [[quiz-convolution-quiz\|Convolution quiz]] | ❓ quiz |  | convolution | core | ✅ done |
| 3 | [[class-pooling\|Pooling]] | 📖 class | Max pooling. |  | optional · ➕ added | ✅ done |
| 4 | [[class-cnn-architectures\|CNN architectures]] | 📖 class |  | cnn-architecture | optional | ⏳ planned |
| 5 | [[exercise-first-cnn\|First CNN]] | 🛠️ project | Train a CNN on the pictures | convolution, cnn-architecture | core | ⏳ planned |

## 2026-11-22 01:08

- Course created
- Class [[class-convolution|Convolution]]
- Exam [[quiz-convolution-quiz|Convolution quiz]] assigned (quiz, 2 questions)
- Exam [[quiz-convolution-quiz]] corrected : 1 A, 1 B (mean 4.5/5)
- Class [[class-pooling|Pooling]]
- Shared [3Blue1Brown - But what is a convolution ?](https://www.youtube.com/watch?v=KuXjwB4LzSA)
- Shared [Old notes](notes.pdf)
- Prefers visual explanations
