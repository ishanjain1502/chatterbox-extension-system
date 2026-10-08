PARALINGUISTIC_TAGS = (
    "[clear throat]",
    "[sigh]",
    "[shush]",
    "[cough]",
    "[groan]",
    "[sniff]",
    "[gasp]",
    "[chuckle]",
    "[laugh]",
)

NONE_TAG = "none"
TAG_TO_INDEX = {NONE_TAG: 0}
for i, tag in enumerate(PARALINGUISTIC_TAGS, start=1):
    TAG_TO_INDEX[tag] = i
INDEX_TO_TAG = {index: tag for tag, index in TAG_TO_INDEX.items()}
NUM_CLASSES = len(TAG_TO_INDEX)
