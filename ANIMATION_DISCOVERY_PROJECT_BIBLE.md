# Personalized Animation Discovery Engine — Project Bible

> **Status:** AUTHORITATIVE PROJECT DIRECTION  
> **Purpose:** Single source of truth for the project, for the student and for any AI/coding model assisting with design, implementation, teaching, debugging, evaluation, or documentation.  
> **Primary repository:** `https://github.com/Feanor1206/movie-rcm-system`  
> **Primary branch observed during planning:** `dev`  
> **Course context:** Final project for an introductory Artificial Intelligence course.  
> **Engineering target:** A serious, production-minded but appropriately scoped full-stack project; approximately 1,000 active web users is a design target, while only a subset is expected to invoke expensive AI functions concurrently.  
> **Domain focus:** Animated films / animation-first discovery.  
> **Language-model choice:** Qwen3 4B, fine-tuned for the project where useful.  

---

# 0. READ THIS FIRST — INSTRUCTIONS FOR ANY AI MODEL HELPING WITH THIS PROJECT

If you are an AI assistant, coding agent, tutor, reviewer, or planning model, **treat this document as the authoritative design contract** unless the user explicitly changes a decision later.

Your role is not merely to generate code. Your role is to help the student **learn and build the system from first principles while preserving the highest practical recommendation/discovery quality that the project can reasonably achieve**.

You MUST preserve the following principles:

1. **This is not an LLM wrapper.**
   - The project may use Qwen3 4B, embeddings, external services, and pretrained models.
   - However, the intelligence of the recommendation/discovery system must not collapse into “send the user prompt to an LLM and ask it for movie titles.”
   - The student must build and understand the main retrieval, recommendation, ranking, constraint, user-modeling, evaluation, and feedback components.

2. **The core product is a Personalized Animation Discovery Engine, not only a rating predictor.**
   - It must answer vague remembered-description searches.
   - It must find titles similar to a reference film.
   - It must recommend according to long-term personal taste.
   - It must satisfy arbitrary natural-language constraints.
   - It must combine these modes when the request contains several at once.

3. **Recommendation means contextual fit.**
   - The target is not merely “predict the movie with the highest expected rating.”
   - The target is “rank the movies that best fit this user, this request, this reference title, and this context right now.”

4. **Teach before hiding complexity.**
   - For core introductory-AI components, explain the mathematical idea before or together with code.
   - Prefer implementations the student can understand line-by-line.
   - Libraries may be used for verification, acceleration, or productionization after the student has implemented/understood the important mechanism.

5. **Do not overengineer the backend.**
   - Spring Boot remains the core business backend.
   - FastAPI is the AI/discovery service.
   - Do not introduce Kafka, Kubernetes, service meshes, or a fleet of microservices without a measured need.

6. **Evaluate every important AI claim.**
   - Do not say one model is “better” because it sounds more sophisticated.
   - Compare models using appropriate offline metrics and controlled experiments.
   - If a simpler model wins, keep the simpler model in the serving path.

7. **Protect the distinction between hard constraints and soft preferences.**
   - “under 120 minutes” may be a hard constraint.
   - “a bit sad” is normally a soft preference.
   - A robust discovery engine must model both correctly.

8. **Qwen3 4B is a language layer, not the sole recommender.**
   - Use it for intent parsing, constraint extraction, relative/reference interpretation, conversational refinement, and grounded explanation.
   - The recommender/ranker determines the movie order.
   - If Qwen is unavailable, the system should degrade gracefully rather than become unusable.

9. **Any substantial code contribution should be accompanied by the reason it exists.**
   - State input, output, assumptions, failure modes, test strategy, and how it affects the final discovery quality.

10. **Keep this project suitable for an introductory AI final while allowing an excellent or outstanding implementation.**
    - The goal is depth, coherence, and evidence—not buzzword quantity.

---

# 1. PROJECT IDENTITY

## 1.1 Official project direction

**Personalized Animation Discovery Engine**

A personalized, context-aware, explainable animation discovery system that combines:

- multi-faceted movie representation,
- classical information retrieval,
- content-based recommendation,
- collaborative filtering,
- matrix factorization,
- hybrid/conditional ranking,
- hard and soft constraint handling,
- reference-aware similarity,
- temporal and negative preference modeling,
- diversity reranking,
- natural-language understanding through a fine-tuned Qwen3 4B layer,
- and rigorous offline evaluation.

## 1.2 Plain-language description

The system should understand:

- **what the user usually likes,**
- **what the user wants right now,**
- **what movie the user may be trying to remember,**
- **what “similar to this movie” means in the current request,**
- **what constraints must not be violated,**
- and **which candidates fit the request best.**

It should then retrieve, rank, diversify, and explain the best animated films for that request.

## 1.3 Final academic description

> **A personalized, context-aware and explainable animation discovery system combining multi-faceted content representation, collaborative learning, conditional ranking, and a fine-tuned language model for natural-language intent understanding.**

## 1.4 What makes this project different from a generic recommender

A generic student recommender often does:

```text
user ratings -> cosine/KNN -> top 10 movies
```

This project instead aims for:

```text
user + long-term taste + recent taste + current natural-language request
+ optional reference title + explicit/implicit constraints
        |
        v
intent understanding + retrieval + recommendation + conditional ranking
        |
        v
best-fit animated films + faithful explanation
```

The **unit of intelligence is contextual fit**, not only predicted rating.

---

# 2. COURSE AND LEARNING GOALS

This is an introductory AI course project, so the system must visibly demonstrate learned AI concepts rather than hide everything behind an API.

## 2.1 Concepts the student should genuinely learn and implement

At minimum:

- data preprocessing,
- feature engineering,
- vector representation,
- one-hot / multi-hot encoding,
- TF-IDF,
- cosine similarity,
- sparse user-item matrices,
- nearest neighbors,
- collaborative filtering,
- loss functions,
- optimization,
- gradient descent / SGD,
- regularization,
- train / validation / test separation,
- overfitting,
- latent factor models,
- ranking metrics,
- hybrid models,
- cold-start handling,
- constraint satisfaction,
- diversity/relevance trade-offs,
- ablation studies,
- model serving and inference boundaries.

Additional high-value learning:

- BPR / pairwise ranking,
- dense semantic retrieval,
- LLM instruction tuning,
- LoRA / QLoRA,
- structured-output evaluation,
- model fallback and production constraints.

## 2.2 “Built from scratch” rule

“From scratch” does **not** mean writing NumPy, PyTorch, tokenizers, or matrix multiplication from machine code.

It means that for the core AI logic, the student should understand and preferably implement the important algorithmic steps instead of replacing them with a single opaque library call.

Examples:

- Good: implement TF, IDF, TF-IDF, normalization, cosine similarity using Python/NumPy.
- Good: implement user-KNN/item-KNN prediction logic.
- Good: implement bias-aware matrix factorization training with SGD.
- Good: implement NDCG@K, Recall@K, MMR.
- Fine later: compare against scikit-learn, Surprise, LightGBM, FAISS, or other optimized libraries.
- Not acceptable as the only AI: `LLM(prompt) -> movie titles`.

---

# 3. SCOPE AND NON-GOALS

## 3.1 In scope

- Animated films as the primary domain.
- Personalized discovery.
- Vague-description title retrieval.
- “Similar to X” discovery.
- Relative similarity: “like X, but less scary / more mature / faster”.
- Natural-language constrained discovery.
- Long-term and recent taste modeling.
- Cold-start onboarding.
- Explicit positive and negative preferences.
- Classical and learned recommendation models.
- Fine-tuned Qwen3 4B for language understanding and explanation.
- Offline evaluation and ablation.
- FastAPI serving.
- Integration with Spring Boot.
- Production-minded caching, timeouts, health/readiness, logging, and graceful fallback.

## 3.2 Explicit non-goals for the core project

Do not spend core project time on:

- building a Netflix-scale distributed system,
- Kubernetes,
- service mesh,
- dozens of microservices,
- Kafka unless an actual measured asynchronous need appears,
- training a 4B LLM from random initialization,
- building a vector database from scratch,
- inventing a novel deep architecture only for appearance,
- image generation,
- streaming video through FastAPI,
- using an LLM as an ungrounded recommendation oracle.

---

# 4. USER CAPABILITIES — WHAT THE FINISHED SYSTEM SHOULD DO

The system should support at least the following discovery modes through one coherent engine.

## 4.1 Remembered-description search

Example:

> “I forgot the title. It was a Japanese animated film where a girl enters a spirit world and her parents become pigs.”

Expected behavior:

- recognize this primarily as a **title retrieval** task,
- extract important clues,
- retrieve candidates,
- rank the likely identity highly,
- ideally return *Spirited Away* in top 1 or top 5.

## 4.2 Reference similarity

Example:

> “Give me something like Coraline.”

The system should compare multiple facets, not only genre.

Possible matching facets:

- visual technique,
- atmosphere,
- themes,
- maturity,
- protagonist profile,
- pacing,
- narrative structure,
- collaborative behavior.

## 4.3 Relative reference recommendation

Example:

> “Something like Coraline but less creepy.”

Interpretation:

- preserve some Coraline-like characteristics,
- reduce the “creepiness/darkness” dimension,
- rank candidates conditionally.

This is not plain similarity search.

## 4.4 Personal recommendation

Example:

> “Recommend something for me.”

Use:

- long-term taste,
- recent taste,
- collaborative latent factors,
- explicit likes/dislikes,
- exploration preference,
- popularity/quality only as supporting signals.

## 4.5 Arbitrary natural-language constrained discovery

Example:

> “I want an animated movie under two hours, not too childish, slightly sad but ultimately uplifting, visually beautiful, no musical, for tonight.”

System responsibilities:

- parse hard constraints,
- parse soft preferences,
- respect negative preferences,
- combine with user taste when appropriate,
- produce ranked candidates based on fit.

## 4.6 Conversational refinement

Example sequence:

1. User: “Give me something melancholic and beautiful.”
2. System returns candidates.
3. User: “Those are too heavy.”

The second message should update the **session intent**, not necessarily the user’s permanent taste profile.

## 4.7 Exploration request

Example:

> “Give me something a bit outside my usual taste, but not completely random.”

This requires controlled novelty/exploration rather than pure exploitation.

---

# 5. CENTRAL FORMALIZATION

The main ranking problem is:

\[
Score(m \mid u, q, r, c)
\]

where:

- \(m\): candidate movie,
- \(u\): user,
- \(q\): current query / intent,
- \(r\): optional reference movie,
- \(c\): context and constraints.

A conceptual score may be:

\[
S(m)=
 w_q S_{query}
 + w_r S_{reference}
 + w_t S_{taste}
 + w_{cf} S_{collaborative}
 + w_s S_{semantic}
 + w_p S_{quality}
 + w_n S_{novelty}
 - P(m)
\]

The exact weights should **not** be permanently chosen by intuition. Start with reasonable values, then tune or learn them using validation data.

## 5.1 Dynamic weights

Weights depend on the request mode.

### Pure personal recommendation

- taste: high,
- collaborative: high,
- query: near zero,
- reference: zero.

### Highly specific natural-language request

- query fit: very high,
- hard constraint satisfaction: mandatory,
- taste: supporting signal.

### “Like movie X”

- reference similarity: high,
- user taste: medium,
- collaborative: supporting.

### New user

- content/profile onboarding: high,
- collaborative latent signal: low until enough interactions exist.

---

# 6. HARD CONSTRAINTS VS SOFT PREFERENCES

This distinction is foundational.

## 6.1 Hard constraints

A candidate violating a hard constraint should normally be filtered out before final ranking.

Examples:

- runtime <= 120 minutes,
- release_year >= 2015,
- not musical,
- target language requirement,
- exclude specific studio/franchise if explicitly requested.

Formally:

\[
HardConstraint(m)=True
\]

Only movies satisfying the hard predicate proceed.

## 6.2 Soft preferences

A soft preference contributes to score instead of acting as a binary filter.

Examples:

- slightly melancholic,
- mature,
- visually stylized,
- Ghibli-like,
- comforting,
- fast-paced.

## 6.3 Relative constraints

Examples:

- “less scary than Coraline”,
- “more mature than Frozen”,
- “faster than Spirited Away”.

A relative preference can be modeled as comparison to the reference film’s facet value.

Example:

\[
creepiness(m) < creepiness(r)
\]

or as a soft penalty:

\[
Penalty(m)=\lambda \max(0, creepiness(m)-target)
\]

---

# 7. HIGH-LEVEL SYSTEM ARCHITECTURE

```text
Frontend — Next.js
      |
      v
Nginx / Reverse Proxy
      |
      v
Spring Boot — Core business backend
      |
      | internal service call
      v
FastAPI — AI / Discovery Service
      |
      +--> Movie representations / indexes
      +--> User taste model
      +--> Classical recommender models
      +--> Matrix factorization artifacts
      +--> Hybrid ranker
      +--> Constraint engine
      +--> Qwen3 4B language layer
      +--> Evaluation / model artifacts
```

## 7.1 Spring Boot ownership

Spring Boot is the source of truth for business data and business rules:

- users,
- authentication / authorization,
- movie catalog business entities,
- ratings,
- favorites,
- watch history,
- interaction events,
- application-facing permissions,
- admin functionality,
- normal non-AI APIs.

## 7.2 FastAPI ownership

FastAPI owns AI-serving concerns:

- discovery orchestration,
- movie feature representations,
- recommendation models,
- latent factors,
- candidate retrieval indexes,
- user taste representations / derived cache,
- query interpretation,
- conditional ranking,
- Qwen inference,
- grounded explanation,
- AI health/readiness/model-state reporting.

## 7.3 Boundary rule

FastAPI should **not become a second business backend**.

It should not independently own canonical user accounts, payment state, or authoritative movie-business data.

---

# 8. CURRENT REPOSITORY CONTEXT AND MIGRATION DIRECTION

The repository currently uses a monorepo structure including:

```text
frontend/
backend/
  springboot/
  fastapi/
ai/
database/
docs/
infrastructure/
```

The current repository documentation contains an older AI direction centered around multiple Qwen stages such as Qwen NLU, Qwen recommender, Qwen ranker, and Qwen explanation.

**That is now considered a legacy design direction.**

The new authoritative direction is:

```text
Qwen3 4B language layer
        |
        v
structured intent / constraints / reference interpretation
        |
        v
MovieDiscoveryEngine
  + classical retrieval
  + content recommendation
  + collaborative recommendation
  + matrix factorization
  + hybrid conditional ranking
  + diversity
        |
        v
grounded result + explanation
```

Do not continue building the old multi-Qwen cascade unless a specific component is experimentally shown to improve the new engine.

---

# 9. MOVIE DISCOVERY ENGINE — CORE MODULES

Recommended conceptual structure:

```text
MovieDiscoveryEngine
├── QueryInterpreter
├── ConstraintEngine
├── MovieRetriever
├── TasteModel
├── SimilarityEngine
├── CollaborativeModel
├── CandidateGenerator
├── ConditionalRanker
├── DiversityReranker
└── ExplanationEngine
```

## 9.1 Request flow

```text
User request
    |
    v
QueryInterpreter
    |
    +--> task type
    +--> reference movie
    +--> hard constraints
    +--> soft preferences
    +--> negative preferences
    +--> relative preferences
    |
    v
Candidate generation from multiple sources
    |
    v
Hard constraint filtering
    |
    v
Feature calculation for (user, query, reference, candidate)
    |
    v
Conditional ranker
    |
    v
Diversity / novelty reranker
    |
    v
Evidence builder
    |
    v
Grounded explanation
```

---

# 10. ANIMATION-SPECIFIC MOVIE REPRESENTATION

A core differentiator of this project is the **animation-specific representation**, because generic `genre + overview` features are too weak.

Represent each movie through multiple feature spaces.

## 10.1 Metadata features

- release year,
- runtime,
- country / region,
- language,
- studio,
- director,
- franchise,
- age classification where available,
- popularity / vote count / rating statistics.

## 10.2 Narrative features

- genre,
- themes,
- story archetypes,
- protagonist type,
- setting,
- coming-of-age,
- romance intensity,
- adventure,
- mystery,
- family,
- identity,
- grief,
- friendship,
- war,
- environment,
- technology,
- self-discovery.

## 10.3 Emotional / tone features

Example controlled taxonomy:

- comforting,
- melancholic,
- whimsical,
- dark,
- eerie,
- tense,
- playful,
- absurd,
- reflective,
- uplifting,
- tragic,
- emotional intensity,
- scariness / creepiness.

## 10.4 Visual / animation features

- 2D hand-drawn,
- traditional/cel-like,
- 3D CGI,
- stylized CGI,
- realistic CGI,
- stop-motion,
- painterly,
- cel-shaded,
- hybrid 2D/3D,
- experimental,
- minimalist,
- highly stylized.

## 10.5 Viewing-experience features

- pacing: slow / medium / fast,
- complexity,
- maturity,
- target audience: child / family / teen / adult,
- humor style,
- musical intensity,
- action intensity,
- dialogue density,
- accessibility / easy-viewing vs demanding.

## 10.6 Learned representations

May include:

- TF-IDF text vector,
- semantic text embedding,
- collaborative latent vector from MF/BPR,
- optional visual embedding in stretch version.

## 10.7 Multi-faceted similarity

Do not collapse all similarity into one opaque number too early.

Useful facet similarities:

\[
Sim_{visual}(A,B)
\]

\[
Sim_{theme}(A,B)
\]

\[
Sim_{tone}(A,B)
\]

\[
Sim_{narrative}(A,B)
\]

\[
Sim_{behavior}(A,B)
\]

This enables requests such as:

- “similar visually”,
- “similar emotionally”,
- “same vibe but not same genre”,
- “like X but more mature”.

---

# 11. USER TASTE MODEL

Do not model a user as one permanent vector only.

Recommended structure:

```text
UserTasteProfile
├── long_term
│   ├── genre
│   ├── themes
│   ├── visual
│   ├── tone
│   ├── narrative
│   └── viewing_experience
├── collaborative_latent
├── recent_taste
├── explicit_positive_preferences
├── explicit_negative_preferences
└── session_intent
```

## 11.1 Long-term profile

A weighted content profile can begin as:

\[
P_u = \frac{\sum_i w_i x_i}{\sum_i w_i}
\]

where:

- \(x_i\) = movie representation,
- \(w_i\) = interaction weight.

Possible interaction signals:

- rating,
- favorite,
- completion percentage,
- repeated watch,
- explicit “not interested”,
- early abandonment,
- recency.

## 11.2 Temporal weighting

Use recency decay where appropriate:

\[
w_t = e^{-\lambda \Delta t}
\]

This prevents old preferences from dominating indefinitely.

## 11.3 Recent taste

Recent behavior is a separate signal rather than simply overwriting long-term taste.

## 11.4 Session intent

The user may temporarily want something different from normal taste.

Example:

- long-term: dark fantasy,
- tonight: light comedy.

The session request should dominate the current recommendation without permanently rewriting the long-term profile.

## 11.5 Negative preference model

Model negative preferences explicitly.

Examples:

- dislikes musicals,
- dislikes jump scares,
- avoids romance,
- avoids a particular studio style.

Do not assume negative preference is merely the mathematical inverse of positive preference.

---

# 12. QUERY / INTENT REPRESENTATION

Qwen3 4B should transform natural language into a structured internal schema.

Example input:

> “Something like Coraline, but less creepy, more playful, under two hours, and no musical.”

Example conceptual output:

```json
{
  "task": "recommendation",
  "reference_titles": ["Coraline"],
  "hard_constraints": {
    "runtime_max_minutes": 120,
    "exclude_musical": true
  },
  "soft_preferences": {
    "playfulness": "increase"
  },
  "relative_preferences": {
    "creepiness": {
      "relation": "less_than_reference"
    }
  },
  "preserve_facets": [
    "dark_fantasy",
    "visual_style"
  ]
}
```

## 12.1 Suggested intent fields

- task type,
- possible remembered-title clues,
- reference titles,
- desired genres,
- undesired genres,
- desired themes,
- undesired themes,
- visual preference,
- tone preference,
- pacing preference,
- maturity/audience preference,
- runtime bounds,
- year bounds,
- country/region/studio/director constraints,
- positive facets,
- negative facets,
- relative comparisons,
- exploration/novelty request,
- strictness/confidence per extracted field.

## 12.2 Parser confidence

Where possible, attach confidence or “hard/soft” classification so ambiguous language does not become an accidental hard filter.

---

# 13. RETRIEVAL SUBSYSTEM

Retrieval is responsible for candidate recall, not final ranking.

Use several candidate sources.

```text
                         Query
                           |
         +-----------------+------------------+
         |                 |                  |
         v                 v                  v
 Sparse text          Dense semantic       Behavioral
 retrieval             retrieval            retrieval
 TF-IDF/BM25            embeddings        MF/Item-CF
         |                 |                  |
         +-----------------+------------------+
                           |
                           v
                  Merge + deduplicate
                           |
                           v
                    candidate pool
```

Target candidate pool for final ranking may be approximately 80–200 movies, depending on catalog size.

## 13.1 Vague-description title retrieval

This is a distinct retrieval task.

Searchable fields should include:

- title,
- aliases,
- overview/plot,
- characters where available,
- setting,
- keywords,
- themes,
- studio/director,
- structured animation taxonomy.

Possible retrieval score:

\[
Score_{recall}
= w_1 S_{TFIDF/BM25}
+ w_2 S_{semantic}
+ w_3 S_{entity}
+ w_4 S_{keyword}
\]

Metrics:

- Recall@1,
- Recall@5,
- MRR.

## 13.2 Sparse retrieval

Implement and understand:

- tokenization basics,
- term frequency,
- document frequency,
- inverse document frequency,
- TF-IDF vectorization,
- cosine similarity.

A later optimized implementation may use BM25 or a search engine, but TF-IDF is important for learning.

## 13.3 Dense retrieval

Add after the classical pipeline is strong.

Use a semantic embedding model or external embedding service to improve natural-language recall.

Dense retrieval is **augmentation**, not a replacement for the educational core.

---

# 14. CORE RECOMMENDER MODELS TO BUILD

## 14.1 Popularity baseline

Purpose:

- sanity baseline,
- fallback,
- cold-start support,
- comparison benchmark.

Avoid raw average rating because a film with one five-star rating can dominate.

Use a confidence-weighted/Bayesian-style score, conceptually:

\[
WR = \frac{v}{v+m}R + \frac{m}{v+m}C
\]

where:

- \(R\) = movie mean rating,
- \(v\) = rating count,
- \(C\) = global mean,
- \(m\) = vote-count confidence threshold.

## 14.2 Content-based recommender

Build movie feature vectors using:

- multi-hot categorical features,
- animation taxonomy,
- TF-IDF text features,
- normalized continuous features.

Implement cosine similarity:

\[
cos(a,b)=\frac{a\cdot b}{||a||||b||}
\]

Use weighted user profile vectors for personalized content matching.

## 14.3 User-based KNN

Educational value:

- user-item matrix,
- similarity,
- neighborhood prediction,
- sparsity.

Implement user similarity and rating/relevance prediction.

It may or may not remain in the production ranking path.

## 14.4 Item-based KNN

Likely more useful in serving than user-KNN for this domain.

Useful for:

- “people who liked this also liked…”,
- reference candidates,
- explainable similarity evidence.

## 14.5 Bias-aware Matrix Factorization — primary learned collaborative model

Model:

\[
\hat r_{ui}=\mu+b_u+b_i+p_u^Tq_i
\]

Loss:

\[
L=\sum_{(u,i)\in R}
(r_{ui}-\hat r_{ui})^2
+\lambda( ||p_u||^2+||q_i||^2+b_u^2+b_i^2 )
\]

Implement SGD updates and understand:

- prediction,
- residual/error,
- gradients,
- learning rate,
- regularization,
- epochs,
- initialization,
- validation,
- overfitting,
- early stopping.

This is one of the project’s strongest educational ML components.

## 14.6 BPR-MF — high-value optional upgrade

Rating prediction and ranking are different goals.

Bayesian Personalized Ranking optimizes pairwise preference:

> user prefers positive item \(i\) over sampled negative item \(j\).

Use BPR if time permits, especially for implicit behavior.

Compare:

- MF-MSE,
- BPR-MF,

using:

- Recall@K,
- NDCG@K,
- HitRate@K.

---

# 15. MULTI-SOURCE CANDIDATE GENERATION

Do not allow a single recommender to control candidate recall.

Example:

```text
Matrix Factorization       -> top 50
Content/Taste retrieval    -> top 40
Item-CF                    -> top 40
Query/semantic retrieval   -> top 50
Popularity/fallback        -> top 20
                              |
                              v
                         merge/dedup
                              |
                              v
                         ~100-200 items
```

Benefits:

- better recall,
- robustness to model failure,
- better cold-start,
- better handling of specific language requests.

---

# 16. CONDITIONAL HYBRID RANKER

The final ranker is a central project contribution.

## 16.1 Candidate feature vector

For each `(user, query, reference, movie)` create features such as:

- MF score,
- item-CF score,
- content similarity,
- user long-term taste match,
- recent taste match,
- query similarity,
- semantic score,
- reference visual similarity,
- reference tone similarity,
- reference theme similarity,
- genre affinity,
- studio affinity,
- director affinity,
- pacing match,
- maturity match,
- novelty,
- movie quality/confidence,
- popularity,
- recency,
- constraint penalties,
- negative-preference penalties.

## 16.2 V1: weighted hybrid

Start interpretable:

\[
S = \sum_k w_k f_k
\]

Normalize component scores before blending.

Weights must be tuned on validation data.

## 16.3 V2: learned ranker

After the feature pipeline is correct, train a ranker.

Educational first option:

- logistic regression implemented/understood from first principles.

Production comparison options:

- LightGBM/XGBoost ranking or classification,
- pairwise ranking model,
- BPR-derived score.

Do not deploy a more complex ranker unless evaluation shows improvement.

---

# 17. REFERENCE-AWARE RECOMMENDATION

“Like movie X” must be multi-dimensional.

Represent reference similarity using facets:

```text
reference_score =
  w_visual    * visual_similarity
+ w_tone      * tone_similarity
+ w_theme     * theme_similarity
+ w_narrative * narrative_similarity
+ w_behavior  * collaborative_similarity
```

Weights depend on language.

Examples:

### “Like Spider-Verse visually”

Increase `w_visual` strongly.

### “Like Your Name emotionally”

Increase tone/theme/emotional weights.

### “Like Coraline but less scary”

Use reference similarity while adding a relative creepiness constraint.

This capability should be a major demo feature.

---

# 18. COLD START

## 18.1 New-user onboarding

Ask the user to choose approximately 5–10 liked films and optionally preference facets.

Example facets:

- 2D / 3D / stop-motion,
- mature / family,
- emotional / comedic / dark,
- fantasy / sci-fi / slice-of-life,
- “avoid musical”.

Immediately build a content/taste profile.

## 18.2 Dynamic collaborative weight

As interactions accumulate, increase collaborative confidence.

Conceptual example:

\[
w_{CF}(u)=min(w_{max}, \frac{n_u}{N}w_{max})
\]

Do not hard-code final values without validation.

## 18.3 New-item cold start

Content and semantic representation allow a new film to be retrieved even before enough collaborative interactions exist.

---

# 19. TEMPORAL PREFERENCE AND SESSION STATE

Use separate layers:

- long-term taste,
- recent taste,
- current session intent.

A single transient query should normally affect the session first.

Only repeated evidence should strongly alter long-term taste.

This reduces accidental preference drift.

---

# 20. DIVERSITY, NOVELTY, AND EXPLORATION

Highest relevance alone can produce boring lists.

## 20.1 MMR reranking

Implement Maximal Marginal Relevance:

\[
MMR(m)=\lambda Rel(m)-(1-\lambda)\max_{j\in S}Sim(m,j)
\]

This balances:

- relevance,
- diversity.

## 20.2 Domain-aware diversity

Possible redundancy penalties:

- same franchise,
- same studio,
- same director,
- nearly identical visual style,
- same dominant theme.

## 20.3 Exploration mode

For “show me something outside my normal taste”, increase novelty while retaining a minimum relevance threshold.

---

# 21. EXPLAINABILITY

Explanations must be **grounded in actual ranker evidence**.

Bad:

> “AI thinks you will like it.”

Good:

> “This ranks highly because its visual style is close to Spider-Verse, it matches the fast pacing you requested, and it avoids the superhero theme you explicitly excluded.”

## 21.1 Evidence object

Before generating natural language, produce structured evidence:

```json
{
  "movie_id": 123,
  "scores": {
    "taste_match": 0.79,
    "reference_visual_match": 0.91,
    "query_match": 0.87,
    "item_cf": 0.68
  },
  "constraints": {
    "runtime": "satisfied",
    "exclude_superhero": "satisfied"
  },
  "evidence": [
    "user frequently likes highly stylized animation",
    "reference visual similarity is high",
    "current request prefers fast pacing"
  ]
}
```

Qwen may verbalize this evidence but must not invent unsupported reasons.

## 21.2 Fallback

If Qwen explanation is unavailable, a deterministic template should still produce a valid explanation.

---

# 22. QWEN3 4B — OFFICIAL ROLE

Qwen3 4B is the selected language model for the project.

It is not the primary recommender.

## 22.1 Core tasks

1. **Intent extraction**
2. **Hard/soft constraint extraction**
3. **Reference interpretation**
4. **Relative preference interpretation**
5. **Conversational refinement**
6. **Remembered-description clue extraction/query rewriting**
7. **Grounded recommendation explanation**

## 22.2 Example

Input:

> “Ghibli vibe but more adult, not too depressing, no musical.”

Structured output should resemble:

```json
{
  "task": "recommendation",
  "style_reference": ["Studio Ghibli"],
  "soft_preferences": {
    "maturity": "adult",
    "emotional_intensity": "medium_or_lower"
  },
  "hard_constraints": {
    "exclude_musical": true
  }
}
```

## 22.3 Fine-tuning approach

Use SFT with LoRA/QLoRA rather than full fine-tuning unless hardware and a clear experiment justify otherwise.

## 22.4 Training dataset target

Initial target: approximately 10k–30k high-quality instructions.

Quality is more important than raw quantity.

Suggested distribution:

- intent extraction,
- constraint extraction,
- relative/reference requests,
- negative preferences,
- conversational refinement,
- remembered-description clue extraction,
- grounded explanation,
- ambiguous/edge cases,
- colloquial Vietnamese,
- English or bilingual examples if the product supports them.

Include realistic Vietnamese requests such as:

- “cho cái gì chill chill thôi”,
- “đừng Disney quá”,
- “vibe Ghibli nhưng người lớn hơn”,
- “kiểu Spider-Verse mà không siêu anh hùng”,
- “buồn nhưng đừng depressing”.

## 22.5 LLM evaluation

Do not evaluate by “sounds good”.

Measure:

- JSON validity,
- schema validity,
- slot/field F1,
- hard-constraint extraction accuracy,
- soft-preference extraction accuracy,
- reference resolution accuracy,
- relative-relation accuracy,
- hallucination/unsupported explanation rate.

Compare:

- base Qwen3 4B,
- fine-tuned Qwen3 4B,
- optional alternative baseline if needed.

## 22.6 Serving fallback

Qwen path must have:

- bounded concurrency,
- timeout,
- request caching where safe,
- graceful fallback to deterministic parser/default strategy,
- health/readiness state.

If Qwen is unavailable, the classical recommender should still function.

---

# 23. SEMANTIC AUGMENTATION

Once the classical core is stable, add semantic embeddings for better natural-language recall.

Possible use cases:

- vague description search,
- theme similarity,
- natural-language request retrieval,
- plot/keyword semantic matching.

Use hybrid sparse+dense retrieval rather than deleting TF-IDF.

Why both:

- sparse retrieval is precise for names/keywords,
- dense retrieval improves paraphrase/semantic recall.

---

# 24. OPTIONAL VISUAL TASTE — HIGH-VALUE STRETCH GOAL

Animation is unusually visual, so a visual representation is a strong domain-specific extension.

Possible inputs:

- posters,
- official keyframes,
- sampled trailer frames where licensing/data handling permits.

Potential capability:

> “I want something that looks like Spider-Verse.”

A visual embedding may become a separate `S_visual` feature rather than replacing textual/content signals.

This is a stretch goal and must not delay the core recommender.

---

# 25. DATA STRATEGY

## 25.1 Data roles

Use different sources for different purposes.

### Interaction data

MovieLens or another legally usable public interaction dataset can provide:

- user ratings,
- user-item interactions,
- collaborative training/evaluation.

### Rich movie metadata

TMDB or other appropriate metadata source may provide:

- overview,
- genres,
- runtime,
- release year,
- cast/director,
- production/studio fields,
- poster metadata,
- external identifiers.

### Animation-specific taxonomy

The project should create or derive its own structured facets for:

- technique,
- visual style,
- tone,
- themes,
- audience/maturity,
- pacing,
- emotional intensity.

## 25.2 Domain filtering challenge

Filtering a general movie dataset down to animation reduces:

- number of items,
- interaction count,
- users with enough animation history.

Therefore:

- measure sparsity after filtering,
- define minimum-interaction rules carefully,
- consider keeping users with enough animation interactions,
- preserve content features to reduce dependence on collaborative density.

## 25.3 Dataset directories

Recommended:

```text
ai/datasets/
├── raw/
├── interim/
├── processed/
├── mappings/
├── splits/
└── schemas/
```

Never overwrite raw data silently.

## 25.4 Reproducibility

Every processed dataset should record:

- source version/date,
- preprocessing code version,
- random seed where applicable,
- filtering criteria,
- train/validation/test strategy.

---

# 26. TRAIN / VALIDATION / TEST STRATEGY

Prefer temporal evaluation where timestamps exist.

Conceptually:

```text
past ---------------------------------------> future
      TRAIN               VALID        TEST
```

Do not randomly leak future behavior into training if the goal is to predict future discovery/recommendation behavior.

Possible per-user split:

- earlier ~80% interactions: train,
- next ~10%: validation,
- latest ~10%: test.

Exact policy depends on data density and must be documented.

---

# 27. EVALUATION — BY SUBSYSTEM

No single metric is sufficient.

## 27.1 Title recall / remembered description

- Recall@1,
- Recall@5,
- MRR.

Build a curated query set containing paraphrases and incomplete descriptions.

## 27.2 Personalized ranking

Primary:

- Recall@K,
- NDCG@K,
- HitRate@K.

Additional:

- Precision@K.

## 27.3 Rating prediction

Only if rating prediction is part of the experiment:

- RMSE,
- MAE.

Do not treat RMSE as the sole measure of recommendation quality.

## 27.4 Beyond-accuracy metrics

- intra-list diversity,
- catalog coverage,
- novelty,
- possibly serendipity with a carefully defined proxy.

## 27.5 Constraint satisfaction

Measure:

- hard constraint satisfaction rate,
- soft preference alignment proxy,
- relative preference satisfaction where possible.

Hard constraints should approach 100% when the catalog contains valid candidates.

## 27.6 Qwen parser

- schema validity,
- JSON validity,
- field/slot F1,
- hard/soft classification accuracy,
- relation extraction accuracy,
- hallucination rate.

## 27.7 End-to-end evaluation set

Create a curated benchmark of approximately 200–500 realistic discovery queries across categories:

- vague recall,
- pure personalized recommendation,
- reference similarity,
- relative reference,
- hard constraints,
- soft constraints,
- negative preferences,
- conversational refinements,
- exploration.

This becomes the project’s signature evaluation asset.

---

# 28. BASELINES AND ABLATION STUDY

## 28.1 Core benchmark table

Compare at least:

1. popularity,
2. content TF-IDF,
3. user-KNN,
4. item-KNN,
5. matrix factorization,
6. hybrid,
7. hybrid + MMR,
8. full contextual system.

If semantic/Qwen features exist, also test:

9. hybrid + semantic,
10. hybrid + semantic + Qwen intent.

## 28.2 Ablation

Evaluate the full system with components removed:

- full − collaborative,
- full − animation-specific features,
- full − temporal taste,
- full − reference facets,
- full − semantic retrieval,
- full − Qwen parser,
- full − diversity rerank.

The goal is to answer:

> Which component actually improves which capability?

Do not assume every added module is beneficial.

---

# 29. FASTAPI API DESIGN

Keep the external AI API small and coherent.

## 29.1 Primary endpoint

```http
POST /v1/discover
```

Example request:

```json
{
  "user_id": 42,
  "query": "something like Coraline but less creepy",
  "limit": 10
}
```

Example conceptual response:

```json
{
  "request_id": "...",
  "intent": {
    "task": "recommendation",
    "reference": "Coraline",
    "relative_preferences": {
      "creepiness": "lower"
    }
  },
  "strategy": {
    "personalized": true,
    "reference_aware": true,
    "constraints_applied": true
  },
  "results": [
    {
      "movie_id": 123,
      "score": 0.89,
      "evidence": {...},
      "explanation": "..."
    }
  ]
}
```

## 29.2 Supporting endpoints

```http
POST /v1/feedback
GET  /healthz
GET  /readyz
```

Optional internal/debug endpoints may expose:

- active model version,
- artifact version,
- parser diagnostics,
- ranker feature debug output,
- only in safe internal/development environments.

## 29.3 Avoid endpoint explosion

Do not create dozens of public endpoints for every model if one unified discovery API can orchestrate them internally.

---

# 30. PROPOSED FASTAPI / AI CODE ORGANIZATION

A recommended target structure:

```text
backend/fastapi/
├── app/
│   ├── main.py
│   ├── api/
│   │   ├── discovery.py
│   │   ├── feedback.py
│   │   ├── health.py
│   │   └── admin.py
│   ├── schemas/
│   ├── dependencies/
│   └── core/
│       ├── config.py
│       ├── logging.py
│       └── metrics.py
│
├── discovery/
│   ├── engine.py
│   ├── query_interpreter/
│   ├── constraints/
│   ├── retrieval/
│   ├── ranking/
│   └── explanation/
│
├── recommender/
│   ├── popularity/
│   ├── content/
│   ├── collaborative/
│   ├── matrix_factorization/
│   ├── hybrid/
│   └── reranking/
│
├── representation/
│   ├── movie/
│   ├── user/
│   ├── semantic/
│   └── visual/
│
├── llm/
│   ├── qwen/
│   ├── intent/
│   ├── explanation/
│   ├── schemas/
│   └── fallback/
│
├── serving/
│   ├── artifact_registry.py
│   ├── lifecycle.py
│   └── concurrency.py
│
└── tests/

ai/
├── datasets/
├── training/
│   ├── content/
│   ├── collaborative/
│   ├── matrix_factorization/
│   ├── ranking/
│   └── qwen/
├── evaluation/
│   ├── metrics/
│   ├── benchmarks/
│   ├── ablation/
│   └── reports/
├── experiments/
└── artifacts/
```

## 30.1 Dependency rule

`recommender/` and core ML code must **not depend on FastAPI**.

The same model should be runnable from:

- unit tests,
- CLI,
- notebook,
- evaluation script,
- API serving.

FastAPI is an adapter/serving layer.

---

# 31. MODEL AND ARTIFACT LIFECYCLE

Every trained artifact should have versioned metadata.

Examples:

- MF latent matrices,
- content feature matrices,
- IDF vocabulary,
- item similarity index,
- semantic index,
- learned ranker,
- Qwen LoRA adapter,
- taxonomy version.

Artifact metadata should include:

- model name/version,
- training dataset version,
- code commit where possible,
- training date,
- hyperparameters,
- metrics,
- feature schema version.

## 31.1 Startup

At FastAPI startup:

1. validate config,
2. load required lightweight artifacts,
3. initialize model registry,
4. load/warm Qwen according to deployment mode,
5. mark readiness only after required components are usable.

## 31.2 Health vs readiness

- `/healthz`: process is alive.
- `/readyz`: required serving artifacts are loaded and requests can be handled.

---

# 32. PERFORMANCE AND SCALE TARGET

The web target is approximately 1,000 active users, but not 1,000 simultaneous Qwen generations.

## 32.1 Cheap path

Precompute/cache where practical:

- movie feature vectors,
- IDF vocabulary,
- item similarities or ANN structures,
- matrix-factor latent vectors,
- static metadata facets,
- user profiles when stable.

Final ranking should usually run over a relatively small candidate set.

## 32.2 Expensive path

Qwen inference is the main expensive component.

Use:

- bounded concurrency,
- request timeout,
- cancellation handling,
- optional queue for expensive operations,
- cache for repeated deterministic parses where safe,
- fallback parser,
- separate metrics for Qwen latency and saturation.

## 32.3 Do not proxy video through AI services

The AI service must never become a video-delivery path.

---

# 33. CACHING

Possible cache layers:

- movie representation cache,
- user taste profile cache,
- popular/trending results,
- semantic search results for repeated queries,
- parsed intents for normalized identical queries,
- recommendation results with short TTL where appropriate.

Cache keys must include model/artifact versions when stale results could be harmful.

Redis is appropriate if shared caching is needed across service replicas.

---

# 34. RELIABILITY AND FALLBACKS

The system should degrade in layers.

Example:

```text
Qwen available?
  yes -> structured intent parser
  no  -> rule/default parser

Semantic index available?
  yes -> sparse + dense retrieval
  no  -> sparse TF-IDF retrieval

Collaborative model available?
  yes -> hybrid ranker
  no  -> content + popularity fallback
```

The site should still produce useful results when one AI component is unavailable.

---

# 35. SECURITY / CONFIGURATION

- Secrets must come from environment/secrets management, not committed source.
- Do not expose FastAPI model-management/debug endpoints publicly in production.
- Spring Boot should normally remain the user-facing authority.
- Validate all request payloads with explicit schemas.
- Limit request size.
- Rate-limit expensive endpoints where necessary.
- Avoid logging private/free-form user text unnecessarily.
- Separate development and production CORS/configuration.

---

# 36. OBSERVABILITY

Track at least:

- request rate,
- p50/p95/p99 endpoint latency,
- discovery latency by stage,
- Qwen parsing latency,
- ranker latency,
- cache hit rate,
- fallback rate,
- parser failure rate,
- candidate count before/after filters,
- no-result rate,
- model/artifact version.

For debugging a single request, use a request ID and stage timings.

---

# 37. PHASED IMPLEMENTATION ROADMAP

Do not start by building the whole final stack.

## Phase 0 — Foundations and data inspection

Learn/build:

- data loading,
- EDA,
- animation filtering,
- dataset sparsity analysis,
- interaction distributions,
- movie metadata inspection.

Deliverables:

- reproducible preprocessing entry point,
- raw/interim/processed data separation,
- dataset report.

Exit gate:

- student can explain what data exists and where biases/sparsity appear.

## Phase 1 — Evaluation framework first

Implement:

- temporal split,
- Precision@K,
- Recall@K,
- HitRate@K,
- NDCG@K,
- RMSE/MAE if needed.

Why first:

- every later model can be measured immediately.

Exit gate:

- one dummy baseline can run through the entire evaluation pipeline.

## Phase 2 — Popularity baseline

Implement confidence-aware popularity ranking.

Exit gate:

- reproducible baseline metrics exist.

## Phase 3 — Animation taxonomy and content representation

Build:

- genre multi-hot,
- animation-specific facets,
- text preprocessing,
- TF-IDF from first principles,
- cosine similarity.

Exit gate:

- similar-title results are qualitatively sensible,
- content recommender has measurable ranking performance.

## Phase 4 — Vague-description sparse retrieval

Build:

- searchable movie documents,
- TF-IDF/BM25-style retrieval,
- curated remembered-description query set.

Exit gate:

- Recall@K/MRR baseline measured.

## Phase 5 — User-KNN and Item-KNN

Implement both to learn them; identify which is useful in serving.

Exit gate:

- metrics compared to popularity/content.

## Phase 6 — Bias-aware Matrix Factorization

Implement:

- latent factors,
- biases,
- SGD,
- regularization,
- early stopping.

Plot/record:

- training loss,
- validation loss,
- ranking metrics.

Exit gate:

- student can derive/explain update logic,
- model beats at least one simpler baseline on a relevant metric or its limitations are understood.

## Phase 7 — Hybrid candidate generation and ranking

Merge candidates from multiple models.

Implement normalized weighted ranker.

Tune weights on validation data.

Exit gate:

- hybrid evaluation exists,
- no hand-waved “best weights”.

## Phase 8 — Cold-start, negative preference, temporal taste

Build:

- onboarding profile,
- dynamic collaborative confidence,
- recency weighting,
- explicit negative preference penalties.

Exit gate:

- new user has useful recommendations,
- temporary session request does not permanently corrupt taste.

## Phase 9 — Constraint engine and reference-aware ranking

Build:

- hard constraints,
- soft preferences,
- relative constraints,
- facet-aware reference similarity.

Exit gate:

- demo queries such as “like X but less scary” behave correctly.

## Phase 10 — MMR diversity and exploration

Add diversity reranking and novelty controls.

Exit gate:

- diversity metric improves without unacceptable NDCG loss.

## Phase 11 — Dense semantic retrieval

Add pretrained/external semantic embeddings.

Use sparse+dense hybrid retrieval.

Exit gate:

- vague/paraphrased query recall improves on the curated benchmark.

## Phase 12 — Unified `/v1/discover`

Create one orchestration path that selects strategies based on parsed request structure.

Exit gate:

- all major query types work through a coherent API.

## Phase 13 — Qwen3 4B dataset

Design:

- intent schema,
- examples,
- edge cases,
- Vietnamese colloquial language,
- train/validation/test split.

Exit gate:

- dataset quality review complete before training.

## Phase 14 — QLoRA fine-tuning Qwen3 4B

Train and compare against base model.

Exit gate:

- measurable parser improvement,
- stable structured output.

## Phase 15 — Conversational refinement and grounded explanation

Integrate session updates and evidence-based explanation.

Exit gate:

- follow-up messages modify the intended dimensions,
- explanations never invent unsupported ranking reasons in the test set.

## Phase 16 — Full ablation and end-to-end evaluation

Produce the final benchmark report.

Exit gate:

- every major final-system component has evidence for its inclusion.

## Phase 17 — Serving hardening

Add:

- cache,
- concurrency limits,
- timeouts,
- readiness,
- structured logs,
- load tests,
- fallback tests.

Exit gate:

- stable under intended project load.

## Phase 18 — Spring Boot integration

Spring Boot becomes the application-facing orchestrator/business layer.

Exit gate:

- frontend does not need to know internal AI implementation details.

## Phase 19 — Final report/demo

Demo should deliberately show multiple intelligence modes, not only a top-10 recommendation screen.

---

# 38. LEARNING ROADMAP — JUST-IN-TIME STUDY

Do not postpone the project until “all math is learned”.

Learn concepts when they become necessary.

## When building cosine/content

Learn:

- vectors,
- dot product,
- norm,
- normalization,
- cosine similarity,
- bag-of-words,
- TF-IDF.

## When building collaborative filtering

Learn:

- matrices,
- sparsity,
- nearest neighbors,
- Pearson/cosine similarity,
- neighborhood weighting.

## When building MF

Learn:

- latent variables,
- objective/loss,
- partial derivatives intuition,
- SGD,
- regularization,
- hyperparameters,
- overfitting.

## When building ranking evaluation

Learn:

- relevance,
- top-K ranking,
- DCG/NDCG,
- precision/recall trade-offs.

## When building Qwen fine-tuning

Learn:

- tokenizer,
- autoregressive language modeling,
- instruction tuning,
- SFT,
- LoRA,
- QLoRA,
- quantization basics,
- structured output evaluation.

---

# 39. QUALITY GATES

A feature is not “done” merely because it runs.

For each AI component, require:

1. clearly defined problem,
2. input/output schema,
3. baseline,
4. unit tests for core math/logic,
5. offline metric,
6. validation comparison,
7. documented failure cases,
8. reason for keeping it in the final system.

## 39.1 Example quality gate — TF-IDF

- hand-check a tiny corpus,
- verify TF and IDF manually,
- compare against a known library on a toy example,
- confirm cosine ordering,
- evaluate on real retrieval queries.

## 39.2 Example quality gate — MF

- training loss decreases,
- validation monitored,
- reproducible seed,
- regularization experiment,
- compare to simple baselines,
- inspect cold-start limitation.

## 39.3 Example quality gate — Qwen

- schema-valid output rate,
- field-level metrics,
- compare base vs fine-tuned,
- test colloquial Vietnamese,
- test ambiguous input,
- fallback behavior.

---

# 40. TESTING STRATEGY

## 40.1 Unit tests

Test mathematical building blocks independently:

- cosine,
- normalization,
- TF-IDF,
- similarity,
- rating prediction,
- MF updates on toy data,
- metrics,
- constraint evaluation,
- MMR selection.

## 40.2 Integration tests

Test:

- artifact load,
- user profile construction,
- candidate generation,
- discovery orchestration,
- FastAPI request/response,
- Spring Boot -> FastAPI contract.

## 40.3 Golden query tests

Maintain a small set of manually reviewed discovery queries whose expected behavior should not regress.

Examples:

- remembered Spirited Away clue,
- “like Coraline but less creepy”,
- “Ghibli vibe but more adult”,
- “under 90 minutes, no musical”,
- personal recommendation with known profile.

---

# 41. TEACHING RULES FOR FUTURE AI ASSISTANTS

When the student asks for help, follow this teaching protocol whenever practical.

## 41.1 Before writing important AI code

Explain:

- what problem this component solves,
- why it is needed in this project,
- core mathematical intuition,
- expected inputs/outputs,
- how it will be evaluated.

## 41.2 While implementing

- Keep initial implementation readable.
- Avoid clever abstractions before correctness.
- Use toy examples.
- Make intermediate values inspectable.
- Include comments for equations/updates, not obvious syntax.

## 41.3 After implementing

Ask/verify:

- Does it pass unit tests?
- Does it beat the baseline?
- What cases fail?
- Does this improve end-to-end discovery?
- Should it remain in the serving path?

## 41.4 Do not silently replace learning opportunities

Examples:

If the current learning goal is TF-IDF, do not simply import a vectorizer and declare the task complete.

If the current learning goal is MF, do not jump directly to a recommender package unless it is being used as a reference implementation.

## 41.5 Coding agents

A coding model may generate boilerplate and tests, but for core AI files it should provide enough explanation that the student can defend the code orally.

Important core files include concepts equivalent to:

- `tfidf.py`,
- `similarity.py`,
- `user_knn.py`,
- `item_knn.py`,
- `matrix_factorization.py`,
- `hybrid_ranker.py`,
- `mmr.py`,
- `metrics.py`,
- constraint scoring,
- intent schema.

---

# 42. ENGINEERING RULES FOR FUTURE CODING MODELS

1. Preserve clear module boundaries.
2. Do not couple core recommender code to FastAPI.
3. Add type hints and explicit schemas.
4. Prefer deterministic/reproducible experiments.
5. Separate training code from serving code.
6. Version artifacts.
7. Never silently change feature schemas between training and serving.
8. Do not load enormous models at import time without lifecycle control.
9. No unbounded expensive concurrency.
10. No hard-coded secrets.
11. No public debug endpoints in production.
12. No database queries inside tight per-candidate ranking loops when features can be batched/preloaded.
13. Avoid N+1 calls across Spring Boot/FastAPI.
14. Every list/retrieval operation must have a clear limit.
15. Every external/model call needs timeout/error handling.
16. Prefer batch vectorized computation over Python loops where performance matters, but only after correctness is clear.

---

# 43. DECISIONS THAT SHOULD NOT BE REOPENED WITHOUT NEW EVIDENCE

These are currently settled:

- Domain focus: animation.
- Product identity: Personalized Animation Discovery Engine.
- Spring Boot: core business backend.
- FastAPI: AI/discovery service.
- Core recommendation must not be delegated entirely to an LLM.
- Qwen3 4B: chosen language model.
- Qwen role: language understanding/refinement/explanation.
- Classical/hybrid recommender remains the core ranking intelligence.
- Multi-faceted animation representation is central.
- Evaluation/ablation is mandatory.
- The main product objective is contextual fit, not only rating prediction.
- One unified discovery flow should support retrieval + recommendation + constraints + reference similarity.

A future model may propose changing one of these only if it states:

1. what new evidence/constraint motivates the change,
2. what measurable benefit is expected,
3. what migration cost exists,
4. how it affects the course-learning objective.

---

# 44. OPTIONAL HIGH-VALUE EXTENSIONS — PRIORITIZED

Only attempt after the core system is strong.

## Tier A — most valuable

1. Visual taste / visual similarity.
2. BPR or learned ranker.
3. Conversational session refinement.
4. Better semantic sparse+dense retrieval.

## Tier B — interesting

5. Group recommendation: “me and my friend/partner”.
6. Controlled exploration mode.
7. Counterfactual discovery: “what if I remove this constraint?”.
8. Why-not explanation: “why did you not recommend X?”.

## Tier C — only if time remains

9. Online/near-online user profile updates.
10. Bandit-style exploration experiments.
11. More sophisticated learning-to-rank.

---

# 45. DEMO PLAN

A good final demo should show the system’s breadth in a few minutes.

Suggested sequence:

1. **Remembered title**
   - vague Spirited Away-style description,
   - show retrieval result.

2. **Reference similarity**
   - “something like Coraline”.

3. **Relative refinement**
   - “less creepy and more playful”.

4. **Personal taste**
   - “recommend something for me”.

5. **Hard + soft constraints**
   - “under two hours, no musical, mature, slightly melancholic”.

6. **Conversational follow-up**
   - “those are too heavy”.

7. **Explainability**
   - show evidence behind one ranked result.

8. **Evaluation slide**
   - show baseline -> content -> CF -> MF -> hybrid -> full system.

This makes the AI contribution visible rather than hiding it behind a polished frontend.

---

# 46. REPORT / PRESENTATION STORY

The academic narrative should be:

1. Generic rating prediction is insufficient for real discovery.
2. Animation has domain-specific visual/emotional/narrative facets.
3. Users have long-term taste but also short-term intent.
4. Discovery requests can be retrieval, similarity, personalization, constraints, or combinations.
5. Therefore the system uses multi-source retrieval and conditional ranking.
6. Classical AI/ML models provide interpretable/reproducible core intelligence.
7. Qwen3 4B translates natural language into structured intent and grounded explanations.
8. Each major component is evaluated separately and through ablation.
9. The final system is served as an AI service integrated with a real web application.

---

# 47. DEFINITION OF SUCCESS

The project is successful if:

- the student can explain the core algorithms without hiding behind libraries,
- the system handles multiple discovery modes coherently,
- recommendation quality improves over simple baselines,
- natural-language constraints are reliably parsed and respected,
- vague-description retrieval works on a curated benchmark,
- reference-aware recommendations react correctly to facet/relative requests,
- cold-start is usable,
- ranked lists are not excessively redundant,
- explanations are grounded,
- Qwen fine-tuning demonstrates measurable task improvement,
- FastAPI serves the models reliably,
- the final architecture remains understandable and defendable in a course presentation.

---

# 48. MINIMUM / EXCELLENT / OUTSTANDING COMPLETION LEVELS

## 48.1 Minimum Strong Version

Must include:

- animation-focused dataset,
- evaluation framework,
- popularity baseline,
- TF-IDF content representation,
- item/user CF experiments,
- matrix factorization,
- hybrid ranker,
- hard/soft constraints,
- reference-aware recommendation,
- vague-description retrieval,
- FastAPI serving,
- final evaluation.

This is already a solid AI final project.

## 48.2 Excellent Version

Add:

- semantic dense retrieval,
- dynamic hybrid weighting,
- temporal preference,
- negative preference modeling,
- MMR diversity,
- Qwen3 4B fine-tuning,
- conversational refinement,
- grounded explanations,
- ablation study.

This is the preferred target.

## 48.3 Outstanding Version

Add selectively:

- visual embeddings/taste,
- BPR or strong learned ranker,
- group recommendation,
- controlled exploration,
- counterfactual/why-not explanation,
- larger curated end-to-end benchmark.

Do not sacrifice core correctness to chase this tier.

---

# 49. PROJECT WORKFLOW FOR EVERY NEW FEATURE

Use this loop:

```text
LEARN
  |
  v
DEFINE THE PROBLEM
  |
  v
IMPLEMENT A SIMPLE VERSION
  |
  v
UNIT TEST
  |
  v
EXPERIMENT
  |
  v
MEASURE AGAINST BASELINE
  |
  +--> worse/no value -> simplify/remove
  |
  +--> useful -> integrate
  |
  v
DOCUMENT FAILURE MODES
```

This workflow is more important than “using the newest model”.

---

# 50. QUESTIONS A FUTURE MODEL SHOULD ASK ITSELF BEFORE ADVISING

Before suggesting a design or implementation, internally check:

1. Does this improve the user’s discovery problem or only add complexity?
2. Does the student still learn the AI principle?
3. Can this component be evaluated?
4. Does it preserve Spring Boot/FastAPI ownership boundaries?
5. Does it preserve classical/hybrid recommender independence from Qwen?
6. Is the feature appropriate for animation?
7. Is this a hard constraint, soft preference, or ranking signal?
8. Does the system need this online, or can it be precomputed offline?
9. What happens when the model/service fails?
10. Can the student defend this decision in front of an instructor?

---

# 51. GLOSSARY

**Candidate generation** — retrieving a manageable set of plausible movies before expensive final ranking.

**Collaborative filtering** — recommending based on user-item interaction patterns rather than only content metadata.

**Content-based recommendation** — recommending items whose content/features match a user profile or reference item.

**Contextual fit** — how well a movie matches the current user + request + constraints + context.

**Hard constraint** — condition a candidate must satisfy.

**Soft preference** — desirable property that affects score but is not mandatory.

**Relative preference** — preference expressed relative to a reference item, e.g. “less dark than X”.

**Cold start** — recommendation problem when a new user or item has little/no interaction data.

**Matrix Factorization (MF)** — latent-factor collaborative model decomposing user-item preferences into lower-dimensional vectors.

**BPR** — pairwise ranking objective for implicit personalized ranking.

**MMR** — Maximal Marginal Relevance, a greedy relevance/diversity reranking method.

**NDCG@K** — ranking metric that rewards relevant items appearing higher in the top-K list.

**MRR** — Mean Reciprocal Rank, useful for remembered-title retrieval where the position of the correct answer matters.

**Ablation study** — remove one component at a time to measure its actual contribution.

**Grounded explanation** — explanation generated only from evidence the system actually used or measured.

---

# 52. FINAL ONE-PARAGRAPH BRIEF FOR ANOTHER MODEL

You are helping build an animation-focused Personalized Movie Discovery Engine for an introductory AI final project. The student wants to learn and implement the important AI components from first principles rather than merely call an external recommender API. The engine must unify remembered-description title retrieval, reference-based similarity, personal taste recommendation, and arbitrary natural-language constrained discovery. Spring Boot is the core business backend; FastAPI is the AI/discovery service. The AI core should include animation-specific content representation, TF-IDF/sparse retrieval, user/item collaborative filtering, bias-aware matrix factorization, multi-source candidate generation, a context-dependent hybrid ranker, hard/soft/relative constraints, cold-start handling, temporal and negative preferences, diversity/MMR, explainability, and rigorous evaluation/ablation. Qwen3 4B is the selected language model and may be fine-tuned with QLoRA for intent/constraint/reference parsing, conversational refinement, vague-description clue extraction, and grounded explanation; it must not replace the recommender/ranker. Optimize for contextual fit and real discovery quality, while keeping the system understandable, measurable, and appropriate for a serious university final project.

---

# 53. IMMEDIATE NEXT STEP

The next development work should begin with **Phase 0 + Phase 1**, not Qwen fine-tuning:

1. inventory the current repository and existing data/code,
2. define the animation dataset and taxonomy,
3. build a reproducible preprocessing pipeline,
4. build the evaluation framework,
5. establish the popularity baseline,
6. then implement content representation and TF-IDF from first principles.

This ordering ensures every later model can be objectively evaluated and prevents the project from becoming an unmeasured collection of AI components.

---

**End of Project Bible.**
