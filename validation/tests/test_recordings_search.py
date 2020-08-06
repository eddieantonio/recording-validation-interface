#!/usr/bin/env python3
# -*- coding: UTF-8 -*-

# Copyright (C) 2018 Eddie Antonio Santos <easantos@ualberta.ca>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""
Unit/Integration tests for the recordings search API.
"""

import pytest  # type: ignore
from django.shortcuts import reverse  # type: ignore
from model_bakery import baker  # type: ignore

MAX_RECORDING_QUERY_TERMS = 3  # TODO: will this be a configuration option?


@pytest.mark.django_db
def test_search_recordings(client):
    """
    General test of the recorings search, in the happy case.
    """

    # Store <enipat>, but search for the normatized form (as itwêwina would
    # offer).
    query = "ê-nipat"
    phrase = baker.make_recipe("validation.phrase", transcription="enipat")
    speaker = baker.make_recipe("validation.speaker")

    # Make two recordings. We want to make sure the query actually works by
    # only retrieving the *relevant* recording.
    recording = baker.make_recipe(
        "validation.recording", phrase=phrase, speaker=speaker, _create_files=True
    )
    unrelated_recording = baker.make_recipe("validation.recording", _create_files=True)

    assert recording.phrase != unrelated_recording.phrase

    response = client.get(
        reverse("validation:search_recordings", kwargs={"query": query})
    )

    assert "Access-Control-Allow-Origin" in response, "Missing requried CORS headers"

    recordings = response.json()
    assert isinstance(recordings, list)
    assert len(recordings) == 1
    recording = recordings[0]
    assert recording.get("wordform") == phrase.transcription
    # TODO: Change field name to "speaker_code"?
    assert "speaker" in recording.keys()
    assert recording.get("gender") in ("M", "F")
    assert recording.get("recording_url").startswith(("http://", "https://"))
    assert recording.get("recording_url").endswith(".m4a")
    assert recording.get("speaker_name") == speaker.full_name
    assert recording.get("anonymous") is False
    assert recording.get("speaker_bio_url").startswith(("http://", "https://"))
    assert speaker.code in recording.get("speaker_bio_url")
    assert recording.get("dialect") == speaker.dialect


@pytest.mark.django_db
def test_search_multiple_recordings(client):
    """
    Test for finding multiple recordings by having a comma in the URI.
    e.g.,

        /recording/_search/form1,form2,form3

    """

    # Create more phrases (and recordings) than queried forms.
    phrases = baker.make_recipe(
        "validation.phrase", _quantity=MAX_RECORDING_QUERY_TERMS + 2
    )
    # We only want three of these word forms
    query_forms = [phrase.transcription for phrase in phrases][
        :MAX_RECORDING_QUERY_TERMS
    ]

    # Ensure each phrase has a recording. Only a subset of these recordings
    # should be returned.
    speaker = baker.make_recipe("validation.speaker")
    recordings = [
        baker.make_recipe("validation.recording", phrase=phrase, speaker=speaker)
        for phrase in phrases
    ]

    response = client.get(
        reverse("validation:search_recordings", kwargs={"query": ",".join(query_forms)})
    )

    assert "Access-Control-Allow-Origin" in response, "Missing requried CORS headers"

    matched_recordings = response.json()
    assert isinstance(matched_recordings, list)
    assert len(matched_recordings) == MAX_RECORDING_QUERY_TERMS
    for recording in matched_recordings:
        assert recording.get("wordform") in query_forms
        assert "speaker" in recording.keys()
        assert recording.get("gender") in "MF"
        assert recording.get("recording_url").startswith(("http://", "https://"))
        assert recording.get("recording_url").endswith(".m4a")

    # The word forms in the response should match ALL of the word forms queried.
    assert set(r["wordform"] for r in matched_recordings) == set(query_forms)


@pytest.mark.django_db
def test_search_recording_not_found(client):
    # Create a valid recording, but make sure we never match it.
    recording = baker.make_recipe("validation.recording")

    # Make the query never matches the only recording in the database:
    query = recording.phrase.transcription + "h"
    response = client.get(
        reverse("validation:search_recordings", kwargs={"query": query})
    )

    recordings = response.json()
    assert "Access-Control-Allow-Origin" in response, "Missing requried CORS headers"
    assert isinstance(recordings, list)
    assert len(recordings) == 0
    assert response.status_code == 404


@pytest.mark.django_db
def test_search_max_queries(client):
    # Create valid recordings, one per phrase, but make too many of them.
    speaker = baker.make_recipe("validation.speaker")
    phrases = baker.make_recipe(
        "validation.phrase", _quantity=MAX_RECORDING_QUERY_TERMS + 1
    )
    recordings = [
        baker.make_recipe("validation.recording", speaker=speaker, phrase=phrase)
        for phrase in phrases
    ]

    # Try fetching the maximum
    query = ",".join(
        phrase.transcription for phrase in phrases[:MAX_RECORDING_QUERY_TERMS]
    )
    response = client.get(
        reverse("validation:search_recordings", kwargs={"query": query})
    )
    assert response.status_code == 200

    # Fetch them!
    query = ",".join(phrase.transcription for phrase in phrases)
    response = client.get(
        reverse("validation:search_recordings", kwargs={"query": query})
    )

    # The request should be denied.
    assert "Access-Control-Allow-Origin" in response, "Missing requried CORS headers"
    assert response.status_code == 414


@pytest.mark.django_db
def test_search_unique_word_forms(client):
    """
    Searching for a word form more than once in a single query should return
    results as if the word form was requested only once.
    """
    # We need a valid phrase/recording
    recording = baker.make_recipe("validation.recording")
    phrase = recording.phrase

    # The query will have the term more than once.
    assert MAX_RECORDING_QUERY_TERMS > 1
    query = ",".join(phrase.transcription for _ in range(MAX_RECORDING_QUERY_TERMS))

    response = client.get(
        reverse("validation:search_recordings", kwargs={"query": query})
    )
    assert response.status_code == 200
    recordings = response.json()
    assert len(recordings) == 1
    assert recordings[0]["wordform"] == phrase.transcription


@pytest.mark.django_db
def test_search_fuzzy_match(client):
    """
    The search should make fuzzy matches with respect to the transcription.
    """

    RECORDINGS_PER_PHRASE = 2

    # First, insert some unvalidated phrases, with non-standard orthography.
    phrases = {
        # 'query': model,
        "pwâwiw": baker.make_recipe("validation.phrase", transcription="pwawiw"),
        "kostâcinâkosiw": baker.make_recipe(
            "validation.phrase", transcription="kostacinakosow"
        ),
        "iskwêsis": baker.make_recipe("validation.phrase", transcription="iskwesis"),
    }

    # Make them searchable by adding a couple recordings.
    recordings = [
        baker.make_recipe("validation.recording", phrase=phrase)
        for phrase in phrases.values()
        # Repeat recordings per phrase, to emulate a real recording session
        for _ in range(RECORDINGS_PER_PHRASE)
    ]
    assert len(recordings) == len(phrases) * RECORDINGS_PER_PHRASE

    # Search for the phrases!
    query = ",".join(key for key in phrases)
    response = client.get(
        reverse("validation:search_recordings", kwargs={"query": query})
    )

    assert response.status_code == 200
    actual_recordings = response.json()
    assert len(actual_recordings) == len(recordings)

    # Make sure all the results are there.
    for query, phrase in phrases.items():
        resultant_recordings = [
            result
            for result in actual_recordings
            if result["wordform"] == phrase.transcription
        ]
        assert len(resultant_recordings) == RECORDINGS_PER_PHRASE
