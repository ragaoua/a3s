# Testing strategy

This document describes the overall approach to tests in this project. It is
aimed at contributors (and my future self) who need to understand why tests are
organized the way they are, and where a new test should go.

## Overall philosophy

I try not to change production code to make testing easier. I think it's an
anti-pattern overall that leads to unnecessarily complex implementations: too
much abstraction, loads of injectable dependencies, hooks that exist only so a
test can reach it. Sometimes I do give in, but it's a deliberate call, and I
only do it when the change is transparent or minimal and the benefits largely
outweigh the cost.

I also don't like monkey patching. It makes tests too reliant on implementation
details and too brittle: they break a lot more that way, often for reasons
unrelated to the behavior under test.

## Unit tests

What defines a "unit" is fluid: sometimes it's a class, sometimes a function.
But if it has one test file, it's a unit.

## Component tests

Component tests are focused on modules (one at a time) located at the boundary
of the system, meaning any module that interacts with / depends on an external
system. They try and prove that one module properly interacts with APIs, DBs,
auth servers, etc.

To make component tests fast, the general idea is to avoid spinning up real
instances of a database, API, or IAM server. Instead, I prefer to provide
fixtures that are simple enough that I can convince myself they are a good
approximation of a DB, API, or whatever. Testing against real dependencies
happens in integration tests.

## Integration tests

Integration tests exercise multiple modules together. The goal is to prove that
hot paths are OK, specifically when factoring in what could be real production
external dependencies.

The LLM is a deliberate exception: I stub it even for integration testing. It's
non-deterministic, which would make these tests flaky for reasons unrelated to
the behavior under test, and hitting a real model on every run is expensive.
Only e2e tests will use a "real" LLM API.

## End-to-end tests

Few e2e tests, basically just proving that hot paths are OK. They spin up real
instances and environments for everything and make sure the whole thing works
together most of the time.
