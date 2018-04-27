# extract_items.praat
#
# 2015 October 1, written by Tim Mills
#
# This script extracts labelled words and sentences from a standard 
# annotation format exported from ELAN.
#
# Extracted items are placed in an appropriate directory (one for 
# sentences, one for words), with a filename consisting of the Cree 
# word being illustrated, followed by an underscore and a timestamp, 
# ending in ".wav". The timestamp (given in milliseconds from the 
# start of the recording) is meant to keep filenames unique when 
# multiple instances of a single item are offered.
#
# When running the script, you must manually indicate the speaker
# by entering an appropriate code.
#

# TODO: Append output to cumulative record file.

# First, set up variables for this run of the script:
form Identify directories and speaker
#	sentence word_directory /Users/timills/Google Drive/Research/21st Century Tools for Indigenous Languages/21st Century Tools for Indigenous Languages/Speech Synthesis/Corpus/ExtractedWordsAndSentences/words/
#	sentence sentence_directory /Users/timills/Google Drive/Research/21st Century Tools for Indigenous Languages/21st Century Tools for Indigenous Languages/Speech Synthesis/Corpus/ExtractedWordsAndSentences/sentences/
	sentence word_directory C:\Users\Timothy\Documents\Altlab\MaskwacisRecordings\Extracted\words\
	sentence sentence_directory C:\Users\Timothy\Documents\Altlab\MaskwacisRecordings\Extracted\sentences\
	word word_filename word_codes.txt
	word sentence_filename sentence_codes.txt
	word session 2015-05-05am
	word speaker abc
endform

wordTierCree = 2
wordTierEnglish = 1
sentenceTierCree = 4
sentenceTierEnglish = 3

# File to contain table that connects sentences to their filenames and vice-versa.
sentence_save$ = sentence_directory$ + sentence_filename$
# Ditto for words
word_save$ = word_directory$ + word_filename$

# Identify objects
soundID = selected("LongSound", 1)
textGridID = selected("TextGrid", 1)

# Set up Info window reporting
#writeInfoLine: session$
wordsExtracted = 0
sentencesExtracted = 0

# Loop through (Cree) word tier.
select textGridID
numIntervals = Get number of intervals: wordTierCree
for currentInterval from 1 to numIntervals
#for currentInterval from 1 to 1

	select textGridID

	# Just work with labelled intervals.
	currentInterval$ = Get label of interval: wordTierCree, currentInterval
	if currentInterval$ <> ""
		startTime = Get start point: wordTierCree, currentInterval
		endTime = Get end point: wordTierCree, currentInterval
		midTime = (startTime + endTime) / 2

		# Determine whether it is an isolated word (sentence tier = "") or an example sentence (sentence tier <> "").
		sentenceInterval = Get interval at time: sentenceTierCree, midTime
		sentenceLabel$ = Get label of interval: sentenceTierCree, sentenceInterval

		# If it's an isolated word:
		if sentenceLabel$ = ""

			# get the English gloss
			englishWordInterval = Get interval at time: wordTierEnglish, midTime
			englishWord$ = Get label of interval: wordTierEnglish, englishWordInterval

			# extract it
			select soundID
			wordID = Extract part: startTime, endTime, "yes"

			# normalize sound levels (some speakers are very quiet)
			Scale peak: 0.99

			# save it as a file in a "words" directory, then clear it from the objects list
			timestamp$ = fixed$(startTime*1000,0)
			# Record duration
			duration = endTime - startTime

			# In case there is a "/" character in the interval name, just take the bit before that:
			slashpoint = index(currentInterval$,"/")
			if slashpoint
				currentWord$ = left$(currentInterval$,slashpoint-1)
			else
				currentWord$ = currentInterval$
			endif

			###
			# Adjust word so that it contains no accented characters, for the filename.
			###
			plainWord$ = currentWord$
			plainWord$ = replace$(plainWord$, "â", "a", 100)
			plainWord$ = replace$(plainWord$, "ê", "e", 100)
			plainWord$ = replace$(plainWord$, "î", "i", 100)
			plainWord$ = replace$(plainWord$, "ô", "o", 100)
			# Also remove parentheses and quotation marks.
			plainWord$ = replace$(plainWord$, "(", "", 100)
			plainWord$ = replace$(plainWord$, ")", "", 100)
			# (Escape sequence for <"> character is <"">.)
			plainWord$ = replace$(plainWord$, """", "", 100)

			filename$ = word_directory$ + plainWord$ + "_" + speaker$ + "_" + session$ + "_" + timestamp$ + ".wav"
			Save as WAV file: filename$
			Remove

			# Report to the user through the Info window
			#appendInfoLine: currentWord$, tab$, englishWord$, tab$, speaker$, tab$, duration, tab$, session$, tab$, filename$
			wordsExtracted = wordsExtracted + 1
			# add same information to the word file
			appendFileLine: word_save$, currentWord$ + tab$ + englishWord$ + tab$ + speaker$ + tab$ + string$(duration) + tab$ + session$ + tab$ + filename$
			
		# End of check that it's an isolated word;
		# Otherwise, it is an example sentence; leave it for the next loop.
		endif
		#End of block checking isolated words versus sentences

	endif
	# End of check that current label is not blank.

endfor
# End loop through word tier

#appendInfoLine: "*** end Words ***"
#appendInfoLine: ""

# Set up sentence reporting
#appendInfoLine: "*** Sentences ***"
#appendInfoLine: "Cree", tab$, "English", tab$, "Keyword(s)", tab$, "Speaker", tab$, "Duration", tab$, "Filename"

# Loop through (Cree) sentence tier.
select textGridID
numIntervals = Get number of intervals: 4
for currentInterval from 1 to numIntervals

	# Identify and extract non-null intervals
	select textGridID
	sentenceLabel$ = Get label of interval: sentenceTierCree, currentInterval
	if sentenceLabel$ <> ""

			#appendInfoLine: "Currently processing interval <" + sentenceLabel$ + ">"

			# extract the whole sentence
			startSentence = Get start point: sentenceTierCree, currentInterval
			endSentence = Get end point: sentenceTierCree, currentInterval
			select soundID
			sentenceID = Extract part: startSentence, endSentence, "yes"
			# save it as a file in a "sentences" directory, then clear it from the objects list
			timestamp$ = fixed$(startSentence*1000,0)

			# Record duration for statistical summary.
			duration = endSentence - startSentence

			# Determine filename:
			select textGridID

			# If there is a word annotation (a labelled interval on the Cree word tier),
			# use that as the filename. This loop should catch any such label.
			wordLabel$ = ""
			wordLabelStart = Get interval at time: wordTierCree, startSentence
			wordLabelEnd = Get interval at time: wordTierCree, endSentence
			for currentWordLabel from wordLabelStart to wordLabelEnd
				currentWordLabel$ = Get label of interval: wordTierCree, currentWordLabel
				if currentWordLabel$ <> ""
					wordLabel$ = currentWordLabel$
				endif
			endfor

			# Otherwise, use the first word (space-delimited) from the sentence text.
			if wordLabel$ = ""
				firstSpace = index(sentenceLabel$, " ")
				# If index=0, search term was not found, so no spaces.
				if firstSpace = 0
					wordLabel$ = sentenceLabel$
				else
					wordLabel$ = left$(sentenceLabel$, firstSpace-1)
				endif
			endif

			# Get English translation too
			midSentenceTime = (startSentence + endSentence)/2
			englishSentenceInterval = Get interval at time: sentenceTierEnglish, midSentenceTime
			englishSentence$ = Get label of interval: sentenceTierEnglish, englishSentenceInterval

			###
			# Adjust word so that it contains no accented characters, for the filename.
			###
			plainWord$ = wordLabel$
			plainWord$ = replace$(plainWord$, "â", "a", 100)
			plainWord$ = replace$(plainWord$, "ê", "e", 100)
			plainWord$ = replace$(plainWord$, "î", "i", 100)
			plainWord$ = replace$(plainWord$, "ô", "o", 100)
			# Also remove parentheses and quotation marks.
			plainWord$ = replace$(plainWord$, "(", "", 100)
			plainWord$ = replace$(plainWord$, ")", "", 100)
			# (Escape sequence for <"> character is <"">.)
			plainWord$ = replace$(plainWord$, """", "", 100)

			filename$ = plainWord$ + "_" + speaker$ + "_" + session$ + "_" + timestamp$ + ".wav"
			filepathname$ = sentence_directory$ + filename$
			#appendInfoLine: "Saving as <" + filepathname$ + ">"
			select sentenceID
			Save as WAV file: filepathname$
			Remove

			# Report to the user through the Info window
			#appendInfoLine: sentenceLabel$, tab$, englishSentence$, tab$, wordLabel$, tab$, speaker$, tab$, duration, tab$, session$, tab$, filename$
			sentencesExtracted = sentencesExtracted + 1
			# add to a delimited file the fields: word, filename, sentence text
			appendFileLine: sentence_save$, sentenceLabel$ + tab$ + englishSentence$ + tab$ + wordLabel$ + tab$ + speaker$ + tab$ + string$(duration) + tab$ + session$ + tab$ + filename$

	endif

endfor
# End loop through sentence tier.

sessionReport$ = "Session <" + session$ + ">; word tokens: " + string$(wordsExtracted) + "; sentence tokens: " + string$(sentencesExtracted)
appendInfoLine: sessionReport$
#appendInfoLine: "*** end Sentences ***"

select soundID
plus textGridID
