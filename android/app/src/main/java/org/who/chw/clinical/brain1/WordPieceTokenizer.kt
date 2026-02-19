package org.who.chw.clinical.brain1

import android.content.Context
import android.util.Log

/**
 * WordPiece tokenizer for MiniLM-L6-v2 (BERT-style).
 *
 * Loads vocab.txt and performs proper subword tokenization:
 * 1. Lowercase input
 * 2. Split on whitespace and punctuation
 * 3. For each word, greedily match the longest vocab prefix
 * 4. Unknown subwords get "##" prefix matching
 * 5. Wrap with [CLS] and [SEP] special tokens
 */
class WordPieceTokenizer(context: Context) {

    companion object {
        private const val TAG = "WordPieceTokenizer"
        private const val VOCAB_PATH = "models/tokenizer/vocab.txt"
        private const val MAX_WORD_CHARS = 100

        const val PAD_TOKEN_ID = 0L
        const val UNK_TOKEN_ID = 100L
        const val CLS_TOKEN_ID = 101L
        const val SEP_TOKEN_ID = 102L
    }

    private val vocab: Map<String, Long>

    init {
        vocab = loadVocab(context)
        Log.d(TAG, "Loaded vocabulary with ${vocab.size} tokens")
    }

    private fun loadVocab(context: Context): Map<String, Long> {
        val map = HashMap<String, Long>(32000)
        context.assets.open(VOCAB_PATH).bufferedReader().useLines { lines ->
            lines.forEachIndexed { index, line ->
                map[line.trim()] = index.toLong()
            }
        }
        return map
    }

    /**
     * Tokenize input text into WordPiece token IDs.
     *
     * @param text Input text
     * @param maxLength Maximum sequence length (including [CLS] and [SEP])
     * @return Triple of (inputIds, attentionMask, tokenTypeIds) all of length maxLength
     */
    fun tokenize(text: String, maxLength: Int = 256): TokenizedInput {
        val tokens = mutableListOf<Long>()
        tokens.add(CLS_TOKEN_ID)

        val words = basicTokenize(text)
        for (word in words) {
            if (tokens.size >= maxLength - 1) break

            val subTokens = wordPieceTokenize(word)
            for (subToken in subTokens) {
                if (tokens.size >= maxLength - 1) break
                tokens.add(subToken)
            }
        }

        tokens.add(SEP_TOKEN_ID)

        val inputIds = LongArray(maxLength) { i ->
            if (i < tokens.size) tokens[i] else PAD_TOKEN_ID
        }
        val attentionMask = LongArray(maxLength) { i ->
            if (i < tokens.size) 1L else 0L
        }
        val tokenTypeIds = LongArray(maxLength) { 0L }

        return TokenizedInput(inputIds, attentionMask, tokenTypeIds)
    }

    /**
     * Basic tokenization: lowercase, split on whitespace and punctuation.
     */
    private fun basicTokenize(text: String): List<String> {
        val lower = text.lowercase()
        val words = mutableListOf<String>()
        val current = StringBuilder()

        for (ch in lower) {
            when {
                ch.isWhitespace() -> {
                    if (current.isNotEmpty()) {
                        words.add(current.toString())
                        current.clear()
                    }
                }
                isPunctuation(ch) -> {
                    if (current.isNotEmpty()) {
                        words.add(current.toString())
                        current.clear()
                    }
                    words.add(ch.toString())
                }
                else -> current.append(ch)
            }
        }

        if (current.isNotEmpty()) {
            words.add(current.toString())
        }

        return words
    }

    /**
     * WordPiece tokenization for a single word.
     *
     * Greedily matches the longest prefix in the vocabulary,
     * then continues with "##" prefixed subwords.
     */
    private fun wordPieceTokenize(word: String): List<Long> {
        if (word.length > MAX_WORD_CHARS) {
            return listOf(UNK_TOKEN_ID)
        }

        val tokens = mutableListOf<Long>()
        var start = 0

        while (start < word.length) {
            var end = word.length
            var found = false

            while (start < end) {
                val substr = if (start > 0) {
                    "##" + word.substring(start, end)
                } else {
                    word.substring(start, end)
                }

                val id = vocab[substr]
                if (id != null) {
                    tokens.add(id)
                    found = true
                    break
                }
                end--
            }

            if (!found) {
                tokens.add(UNK_TOKEN_ID)
                break
            }

            start = end
        }

        return tokens
    }

    private fun isPunctuation(ch: Char): Boolean {
        val code = ch.code
        // ASCII punctuation ranges
        if (code in 33..47 || code in 58..64 || code in 91..96 || code in 123..126) {
            return true
        }
        // Unicode general punctuation
        return Character.getType(ch).toByte() in listOf(
            Character.CONNECTOR_PUNCTUATION.toByte(),
            Character.DASH_PUNCTUATION.toByte(),
            Character.END_PUNCTUATION.toByte(),
            Character.FINAL_QUOTE_PUNCTUATION.toByte(),
            Character.INITIAL_QUOTE_PUNCTUATION.toByte(),
            Character.OTHER_PUNCTUATION.toByte(),
            Character.START_PUNCTUATION.toByte()
        )
    }

    data class TokenizedInput(
        val inputIds: LongArray,
        val attentionMask: LongArray,
        val tokenTypeIds: LongArray
    )
}
