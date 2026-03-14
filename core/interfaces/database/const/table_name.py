import enum

Anilist_Prefix = "Anilist"


class TableNames(enum.Enum):
    AnilistMedia = f"{Anilist_Prefix}Media"
    AnilistAiringSchedule = f"{Anilist_Prefix}AiringSchedule"
    AnilistMediaTitle = f"{Anilist_Prefix}MediaTitle"
    AnilistUser = f"{Anilist_Prefix}User"
    ServiceCreds = "ServiceCreds"
    ServiceMediaMapping = "ServiceMediaMapping"
    LocalMedia = "LocalMedia"
