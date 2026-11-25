import re, sys, glob
R = [
 (r"n°1","numéro 1"),(r"1ʳᵉ","première"),(r"1er\b","premier"),(r"35 000ᵉ","trente-cinq millième"),(r"2ᵉ","deuxième"),(r"3ᵉ","troisième"),(r"7ᵉ","septième"),(r"(\d+)ᵉ",r"\1 ième"),
 (r"\bsetters?\b", lambda m: "sètteurs" if m.group(0).lower().endswith("s") else "sètteur"),
 (r"\bclosers\b", "clôzeurs"),
 (r"\b(le|un|du|au|aucun|chaque|son|ton|votre|leur|ce|cet|meilleur|nouveau|futur|bon|d'un|l'|Jr|junior|de|poste de|manager des|grille du|1:1 des|handbook|bootcamp|gates du|siège de|rôle de)\s+closer\b", r"\1 clôzeur"),
 (r"(?i)^(closer|B C .*?, closer)", lambda m: m.group(0).replace("closer","clôzeur").replace("Closer","Clôzeur")),
 (r"\bcloser\b", "clôzer"),
 (r"\bclosing\b","clôzing"),(r"\bclosés?\b",lambda m:"clôzé"+("s" if m.group(0).endswith("s") else "")),
 (r"\bclose(s|r)?\b",lambda m:"clôze"+(m.group(1) or "")),(r"\bclose\b","clôze"),
 (r"\bself-sets?\b","self-sètte"),(r"\bsets?\b",lambda m:"sèttes" if m.group(0).lower().endswith("s") else "sètte"),
 (r"\bno-shows?\b","nô-chô"),(r"\bshows?\b","chô"),(r"\bshow rate\b","chô rète"),
 (r"\bleads?\b",lambda m:"lides" if m.group(0).lower().endswith("s") else "lide"),
 (r"\bleaders?\b",lambda m:"lideurs" if m.group(0).lower().endswith("s") else "lideur"),
 (r"\bleaderboards?\b","lideur-bordes"),(r"\brole plays?\b","rôle plé"),(r"\bgame tape\b","guéïme tèïpe"),
 (r"\bpipeline\b","païpe-laïne"),(r"\bbootcamp\b","boute-campe"),(r"\bdiscovery\b","discovèri"),
 (r"\breferrals?\b",lambda m:"rifèrrals" if m.group(0).lower().endswith("s") else "rifèrral"),
 (r"\bkickoffs?\b","kik-off"),(r"\bhunt\b","heunte"),(r"\bchurn\b","tcheurne"),(r"\bfarm system\b","farme système"),
 (r"\binbound\b","inne-baounde"),(r"\boutbound\b","aoute-baounde"),(r"\bspeed[- ]to[- ]lead\b","spide tou lide"),
 (r"\bworkshops?\b","worke-chope"),(r"\bdeals?\b",lambda m:"diles" if m.group(0).lower().endswith("s") else "dile"),
 (r"\bfunnel\b","feunnel"),(r"\bgates?\b",lambda m:"guéïtes" if m.group(0).lower().endswith("s") else "guéïte"),
 (r"\bshout-outs?\b","chaoute-aoute"),(r"\bcall notes\b","cole notes"),(r"\bnurture\b","neurtcheur"),
 (r"\bopt-ins?\b","opte-inne"),(r"\bmanagers?\b",lambda m:"manadjeurs" if m.group(0).lower().endswith("s") else "manadjeur"),
 (r"\bmanaging\b","manadjinng"),(r"\bpitch\b","pitche"),(r"\bramp\b","rampe"),(r"\bfeedback\b","fidebak"),
 (r"\bskills?\b","skills"),(r"\bSales\b","Sèïlz"),(r"\bTeams\b","Tims"),(r"\bStart Here\b","Starte Hir"),
 (r"\bStrategy\b","Stratédji"),(r"\bRecruiting\b","Ricrouting"),(r"\bTraining\b","Tréning"),
 (r"\bWho to Look For\b","Hou tou louk for"),(r"\bHormozi\b","Hormozi"),(r"\bjunior\b","djunior"),
 (r"\bstretch\b","strètche"),(r"\bbump\b","beumpe"),(r"\bloops?\b",lambda m:"loupes" if m.group(0).lower().endswith("s") else "loupe"),
 (r"\bmindset\b","maïnde-sètte"),(r"\bsavages\b","savèdjes"),(r"\bbridge\b","bridje"),
]
for f in sorted(glob.glob(sys.argv[1]+"/*.txt")):
    t=open(f,encoding="utf-8").read()
    for a,b in R: t=re.sub(a,b,t,flags=re.I)
    open(f,"w",encoding="utf-8").write(t)
