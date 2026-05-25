# Testing strategy

This document describes the overall approach to tests in this project. It is
aimed at contributors (and my future self) who need to understand why tests are
organized the way they are, and where a new test should go.

## Overall philosophy

I try not to change production code to make testing easier. I think it's an
anti-pattern overall that leads to unnecessarily complex implementations: too
much abstraction, loads of injectable dependencies, hooks that exist only so a
test can reach in. Sometimes I do give in, but it's a deliberate call, and I
only do it when the change is transparent or minimal and the benefits largely
outweigh the cost.

I also don't like monkey patching. It makes tests too reliant on implementation
details and too brittle: they break a lot more that way, often for reasons
unrelated to the behavior under test.

## Unit tests

What defines a "unit" is fluid: sometimes it's a class, sometimes a function.
But if it has one test file, it's a unit.

## Component tests

Component tests are focused on one module. Sometimes that module calls on to
other ones, but that just means I didn't deem it relevant to test those modules
separately.

Component tests differ from integration tests in that they don't specifically
aim at testing different modules together. It may happen, but it's a happy
accident, not a goal. Instead, they try to prove that the code properly
interacts with external dependencies (APIs, DBs, auth servers, etc.).

To make component tests fast, the general idea is to avoid spinning up real
instances of a database, API, or IAM server. Instead, I prefer to provide
fixtures that are simple enough that I can convince myself they are a good
approximation of a DB, API, or whatever. Testing against real dependencies
happens in integration tests.

## Integration tests

Integration tests exercise multiple modules together. The goal is to prove that
hot paths are OK, specifically when factoring in what could be real production
external dependencies.

## End-to-end tests

Few e2e tests, basically just proving that hot paths are OK. They spin up real
instances and environments for everything and make sure the whole thing works
together most of the time.
