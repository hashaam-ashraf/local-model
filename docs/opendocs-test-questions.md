# Test questions for the `opendocs` knowledge base

`kb/opendocs/` holds 21,869 markdown pages (about 108 MB) copied from seven open documentation sets. File names are `<source>__<path>.md`, so they are unique and can be uploaded as they are.

| Source | Pages | Size | Licence | Repository |
|---|---|---|---|---|
| MDN Web Docs | 14,758 | 59 MB | CC BY-SA 2.5 | github.com/mdn/content (`files/en-us/`) |
| GitHub Docs | 3,789 | 21 MB | CC BY 4.0 | github.com/github/docs (`content/`) |
| Kubernetes documentation | 1,657 | 16 MB | CC BY 4.0 | github.com/kubernetes/website (`content/en/docs/`) |
| Docker documentation | 916 | 7.1 MB | Apache-2.0 | github.com/docker/docs (`content/`) |
| The Turing Way handbook | 484 | 3.4 MB | CC BY 4.0 | github.com/the-turing-way/the-turing-way (`book/website/`) |
| FastAPI documentation | 154 | 1.5 MB | MIT | github.com/fastapi/fastapi (`docs/en/docs/`) |
| The Rust Programming Language | 111 | 1.2 MB | MIT / Apache-2.0 | github.com/rust-lang/book (`src/`) |

GitHub Docs and Docker pages contain template tags such as `{% data variables... %}`; they are left as they are.

Every expected answer below was checked against the page named in the last column.

## Answerable from one page

| # | Question | Expected answer | Source page |
|---|---|---|---|
| 1 | What are the three ownership rules in Rust? | Each value has an owner; there can only be one owner at a time; when the owner goes out of scope, the value is dropped. | `rust-book__ch04-01-what-is-ownership.md` |
| 2 | Which integer type does Rust use by default? | `i32` | `rust-book__ch03-02-data-types.md` |
| 3 | How many bytes is a Rust `char`? | 4 bytes; it holds a Unicode scalar value. | `rust-book__ch03-02-data-types.md` |
| 4 | What happens on integer overflow in a Rust release build? | Two's complement wrapping (a debug build panics instead). | `rust-book__ch03-02-data-types.md` |
| 5 | What does `cargo check` do? | Checks that the code compiles without producing an executable. | `rust-book__ch01-03-hello-cargo.md` |
| 6 | How do I make a Rust program abort instead of unwinding on panic? | Add `panic = 'abort'` to the relevant `[profile]` section of `Cargo.toml`. | `rust-book__ch09-01-unrecoverable-errors-with-panic.md` |
| 7 | What command starts a FastAPI app in development mode? | `fastapi dev main.py` | `fastapi__fastapi-cli.md` |
| 8 | Where is the alternative ReDoc documentation served in FastAPI? | `http://127.0.0.1:8000/redoc` | `fastapi__tutorial__first-steps.md` |
| 9 | How many times may a FastAPI dependency use `yield`? | Once per dependency. | `fastapi__tutorial__dependencies__dependencies-with-yield.md` |
| 10 | What is the default grace period when a Kubernetes Pod is terminated? | 30 seconds (`terminationGracePeriodSeconds`). | `kubernetes__concepts__workloads__pods__pod-termination.md` |
| 11 | What are the possible phases of a Pod? | Pending, Running, Succeeded, Failed, Unknown. | `kubernetes__concepts__workloads__pods__pod-lifecycle.md` |
| 12 | What port range does a NodePort Service use by default? | 30000-32767 | `kubernetes__concepts__services-networking__service.md` |
| 13 | How many old ReplicaSets does a Deployment keep by default? | 10 (`.spec.revisionHistoryLimit`). | `kubernetes__concepts__workloads__controllers__deployment.md` |
| 14 | What is the default max surge during a Deployment rolling update? | 25%, so at most 125% of the desired Pods are up. | `kubernetes__concepts__workloads__controllers__deployment.md` |
| 15 | How long before a Deployment rollout is reported as stalled? | 600 seconds by default (`progressDeadlineSeconds`). | `kubernetes__tasks__run-application__update-deployment-rolling.md` |
| 16 | What is the default scale-down stabilization window of the Horizontal Pod Autoscaler? | 300 seconds. | `kubernetes__concepts__workloads__autoscaling__horizontal-pod-autoscale.md` |
| 17 | What is an ExternalName Service? | A Service without selectors that uses DNS names instead. | `kubernetes__concepts__services-networking__service.md` |
| 18 | What do the FAIR principles stand for? | Findable, Accessible, Interoperable, Reusable. | `turing-way__afterword__glossary.md` |
| 19 | In The Turing Way, what is the difference between reproducible and replicable research? | Reproducible: same data, same analysis. Replicable: different data, same analysis. | `turing-way__reproducible-research__overview__overview-definitions.md` |
| 20 | What is the minimum number of participants for a Turing Way Book Dash? | 15 | `turing-way__community-handbook__bookdash__bookdash-application.md` |
| 21 | How far ahead does the Book Dash call for applications open? | At least two months in advance. | `turing-way__community-handbook__bookdash__bookdash-application.md` |
| 22 | What does HTTP status code 418 mean? | I'm a teapot. | `mdn__web__http__reference__status__418__index.md` |
| 23 | Which HTTP status code means the client sent too many requests? | 429 Too Many Requests. | `mdn__web__http__reference__status__429__index.md` |
| 24 | What is Docker's default network driver? | `bridge` | `docker__manuals__engine__network__drivers___index.md` |
| 25 | Which port does the kubelet API listen on? | TCP 10250 | `kubernetes__reference__networking__ports-and-protocols.md` |
| 26 | In which directories can a CODEOWNERS file be placed? | `.github/`, the repository root, or `docs/`. | `github-docs__repositories__managing-your-repositorys-settings-and-features__customizing-your-repository__about-code-owners.md` |

## Needs the right source among similar ones

The same wording appears in more than one documentation set, so these check that retrieval picks the right one.

| # | Question | Expected answer | Source page |
|---|---|---|---|
| 27 | How much data can a Kubernetes ConfigMap hold? | At most 1 MiB. | `kubernetes__concepts__configuration__configmap.md` |
| 28 | In the FastAPI request body limits example, what is the limit for `POST /uploads/small`? | 10 MiB (the app limit is 1 MiB, the router limit 100 MiB). | `fastapi__advanced__request-body-limits.md` |
| 29 | What does robust mean for a research result, compared with generalisable? | Robust: same data, different analysis. Generalisable: different data, different analysis. | `turing-way__reproducible-research__overview__overview-definitions.md` |
| 30 | What is the size limit of a single Kubernetes Secret? | 1 MiB. | `kubernetes__concepts__configuration__secret.md` |

## Not in the knowledge base

The assistant should say it does not know instead of answering from general knowledge.

| # | Question |
|---|---|
| 31 | How do I refund a Tangerpay payment? |
| 32 | What is the boiling point of ethanol? |
| 33 | What cash rate does the Reserve Bank of Australia currently set? |
| 34 | How do I define a model in Laravel? |
| 35 | Who is the chief executive of the Alan Turing Institute? |
