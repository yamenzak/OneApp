"""The capabilities a feature can ask for, in one place.

A capability is the question an app asks the catalogue: "give me the models
that can do this". It is deliberately coarser than a provider's task list —
Cloudflare distinguishes Image Classification from Object Detection and Google
does not name tasks at all, and no app cares about that difference at the point
where it picks a model.

Canonical here, emitted into the doctype Select by scripts/gen_doctypes.py and
into the SPA by scripts/gen_frontend.py. At runtime both apps read it back off
the doctype meta rather than keeping a third copy.
"""

# capability -> the provider task names that map onto it. The right-hand side is
# what the sync matches against, lowercased; anything unmatched lands as a model
# needing review rather than being guessed into the nearest bucket.
CAPABILITIES = {
    "Text Generation": ["text generation", "generatecontent", "chat"],
    "Text Embeddings": ["text embeddings", "embedcontent", "embedding"],
    "Reranking": ["text reranking", "reranker", "rerank"],
    "Classification": ["text classification", "image classification", "classification"],
    "Summarization": ["summarization"],
    "Translation": ["translation"],
    "Image Generation": ["text-to-image", "image-to-image", "image generation"],
    "Video Generation": ["text-to-video", "video generation"],
    "Audio Generation": ["text-to-audio", "music generation", "audio generation"],
    "Image Understanding": ["image-to-text", "image to text", "visual question answering"],
    "Speech to Text": ["automatic speech recognition", "speech recognition", "transcribe"],
    "Text to Speech": ["text-to-speech", "text to speech", "tts"],
    "Object Detection": ["object detection"],
}

CAPABILITY_NAMES = list(CAPABILITIES)

# For a Frappe Select.
OPTIONS = "\n".join(CAPABILITY_NAMES)
