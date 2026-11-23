"""Legacy five-aspect examples for the deployed sentiment + aspect models.

The proposed nine-aspect, multi-label taxonomy lives in ml/aspect_taxonomy.py.
Do not relabel these seed rows automatically or merge them into v2 experiments.

These are invented training examples in three input styles:
  en      = English
  tl      = Filipino / Tagalog (office names and document acronyms such as
            TOR, ID, registrar, cashier do not count as English)
  taglish = Taglish, i.e. English and Filipino mixed in one comment

Sentiment labels are: positive, negative, constructive.
  positive     = the student is satisfied.
  negative     = the student complains and does NOT suggest anything.
  constructive = a complaint (or a problem noticed) PLUS a suggestion or
                 request for improvement, e.g.
                 "Matagal ang pila, sana magdagdag ng isa pang window."
                 Constructive rows usually contain a cue word such as
                 sana, dapat, please, should, hopefully, mas okay kung...

Labeling rules (keep these when you add real comments):
  * One aspect per comment: label the MAIN thing the comment is about.
  * Generic comments about nothing in particular ("Very good!") use the
    empty aspect "". The sentiment model learns from them; the aspect
    model skips them (see ml/train.py).
  * If a comment complains AND suggests something, it is constructive,
    never negative.
  * "Hindi / di / wala" flips meaning: "Hindi mabilis" is negative,
    "Hindi naman matagal" is positive.
  * Do not put suggestion words (sana, please, dapat, should...) in
    plain negative or positive rows. That would teach the model that
    those words are not a constructive signal.

Stage real anonymized annotations through ml.review_workflow (v1) or
ml.aspect_transition (v2), following docs/aspect-transition-v2.md.
The legacy ml.train command replaces production models; do not use it for imports.
Keep an independent held-out test set of REAL comments only. Never train on it.
"""

ASPECTS = (
    "processing_time",
    "staff_responsiveness",
    "communication_clarity",
    "service_accessibility",
    "facility_conditions",
)
SENTIMENTS = ("positive", "negative", "constructive")
LANGUAGES = ("en", "tl", "taglish")

# (text, aspect_code, sentiment, language)
EXAMPLES: list[tuple[str, str, str, str]] = [
    # =====================================================================
    # processing_time / negative
    # =====================================================================
    ("Sobrang tagal magrelease ng TOR. Three weeks na ako naghihintay.", "processing_time", "negative", "taglish"),
    ("The queue at the registrar is extremely long and I waited four hours.", "processing_time", "negative", "en"),
    ("Ang tagal ng processing ng documents, sayang oras namin.", "processing_time", "negative", "tl"),
    ("Waited the whole morning just to get my certificate of enrollment.", "processing_time", "negative", "en"),
    ("Grabe yung pila, mabagal magprocess yung window.", "processing_time", "negative", "tl"),
    ("Document release is too slow during enrollment week.", "processing_time", "negative", "en"),
    ("Matagal bago ma-claim yung good moral, almost one month.", "processing_time", "negative", "taglish"),
    ("The cashier line does not move. Very delayed service.", "processing_time", "negative", "en"),
    ("Hassle maghintay. Sobrang tagal bago tawagin yung number ko.", "processing_time", "negative", "taglish"),
    ("It took days before my payment was posted. Too slow.", "processing_time", "negative", "en"),
    ("Mahaba ang pila sa admissions, nakaka-stress maghintay.", "processing_time", "negative", "taglish"),
    ("Processing time for ID replacement is unacceptable.", "processing_time", "negative", "en"),
    ("Ang bagal mag-issue ng receipt. Sayang araw.", "processing_time", "negative", "taglish"),
    ("I stood in line from 8am to 12nn. Terrible turnaround.", "processing_time", "negative", "en"),
    # new: noisy typing, negation, Taglish
    ("Sobrang tagaaaal ng pila grabe, 3 hrs na ako dito", "processing_time", "negative", "taglish"),
    ("Hindi mabilis magprocess yung window, inabot ako ng lunch.", "processing_time", "negative", "tl"),
    ("wla pa din yung TOR ko, 2 weeks na. ang tagal tlga", "processing_time", "negative", "tl"),
    ("Super slow ng cashier today, mahaba pa yung pila.", "processing_time", "negative", "taglish"),
    # =====================================================================
    # processing_time / positive
    # =====================================================================
    ("Mabilis magprocess ng TOR. Finished in thirty minutes.", "processing_time", "positive", "taglish"),
    ("The registrar released my documents quickly. Very efficient.", "processing_time", "positive", "en"),
    ("Maikli lang yung pila today. Fast service, salamat.", "processing_time", "positive", "taglish"),
    ("Payment posting was immediate. Great turnaround time.", "processing_time", "positive", "en"),
    ("On time yung release ng grades. Hindi na kailangan maghintay ng matagal.", "processing_time", "positive", "taglish"),
    ("Admissions processed my papers the same day. Impressive speed.", "processing_time", "positive", "en"),
    ("Mabilis at maayos yung window 3. No long queue.", "processing_time", "positive", "taglish"),
    ("Library clearance was done in minutes. Fast processing.", "processing_time", "positive", "en"),
    ("Hindi na ako naghintay ng matagal. Quick service sa cashier.", "processing_time", "positive", "taglish"),
    ("Same-day release of my certificate. Thank you.", "processing_time", "positive", "en"),
    # new
    ("Hindi naman matagal, mabilis lang actually yung release.", "processing_time", "positive", "taglish"),
    ("mbilis lng po process, thank u po", "processing_time", "positive", "tl"),
    ("Walang masyadong pila today, quick lang yung transaction ko.", "processing_time", "positive", "taglish"),
    ("Fast yung processing ng clearance, natapos agad within the hour.", "processing_time", "positive", "taglish"),
    # =====================================================================
    # processing_time / constructive  (complaint + suggestion)
    # =====================================================================
    ("The registrar line is too long; please open more windows during enrollment.", "processing_time", "constructive", "en"),
    ("Releasing the TOR takes weeks. It would help if there was an online tracking system.", "processing_time", "constructive", "en"),
    ("Waiting four hours for one document is too much, maybe a number queue system can fix this.", "processing_time", "constructive", "en"),
    ("The cashier is slow at peak hours; I suggest adding one more teller.", "processing_time", "constructive", "en"),
    ("Processing of IDs takes too long. Hopefully they can set a fixed release schedule.", "processing_time", "constructive", "en"),
    ("Payment posting is delayed. They should send an SMS once it is already posted.", "processing_time", "constructive", "en"),
    ("Matagal ang pila sa registrar, sana magdagdag ng isa pang window.", "processing_time", "constructive", "tl"),
    ("Sobrang tagal ng release ng TOR, dapat may online tracking para hindi na kami pabalik-balik.", "processing_time", "constructive", "tl"),
    ("Mabagal po ang processing ng good moral, sana po mapabilis kahit konti.", "processing_time", "constructive", "tl"),
    ("Ang haba ng pila sa cashier, mas mainam kung may hiwalay na bintana para sa mga nagmamadali.", "processing_time", "constructive", "tl"),
    ("Sobrang tagal ng queue sa registrar, please add more windows during enrollment week.", "processing_time", "constructive", "taglish"),
    ("Ang bagal ng processing ng TOR, suggest ko na gumawa ng online request system.", "processing_time", "constructive", "taglish"),
    ("Hindi umuusad yung line sa cashier, sana mag-open ng another counter pag peak hours.", "processing_time", "constructive", "taglish"),
    ("Three weeks na yung request ko, mas okay kung may SMS update para di na kami pabalik-balik.", "processing_time", "constructive", "taglish"),
    ("Mabagal yung release ng grades, pwede bang i-post na lang online para di na pumila?", "processing_time", "constructive", "taglish"),
    ("Ang tagal maghintay sa admissions. Hopefully magkaroon ng appointment slots.", "processing_time", "constructive", "taglish"),
    # =====================================================================
    # staff_responsiveness / negative
    # =====================================================================
    ("Yung staff masungit. Hindi ako tinulungan nung nagtanong ako.", "staff_responsiveness", "negative", "tl"),
    ("The clerk was rude and dismissed my question.", "staff_responsiveness", "negative", "en"),
    ("Walang tao sa desk for a long time. Nobody assisted students.", "staff_responsiveness", "negative", "taglish"),
    ("Bastos yung guard sa pila, hindi magalang magsalita.", "staff_responsiveness", "negative", "tl"),
    ("Staff would not look up from their phones. Unhelpful.", "staff_responsiveness", "negative", "en"),
    ("Hindi sumasagot yung personnel. Parang abala ako sa kanila.", "staff_responsiveness", "negative", "tl"),
    ("They told me to come back without explaining why. Very dismissive.", "staff_responsiveness", "negative", "en"),
    ("Ang init ng ulo nung staff. Hindi accommodating.", "staff_responsiveness", "negative", "taglish"),
    ("I was ignored even if I was next in line. Poor customer service.", "staff_responsiveness", "negative", "en"),
    ("Magaspang magsalita. Nakakahiya sa harap ng ibang students.", "staff_responsiveness", "negative", "taglish"),
    ("Frontline staff are hard to reach and never return calls.", "staff_responsiveness", "negative", "en"),
    ("Hindi approachable yung people sa window. Nakakatakot magtanong.", "staff_responsiveness", "negative", "taglish"),
    # new
    ("Hindi helpful yung staff, parang naiistorbo sila pag nagtatanong.", "staff_responsiveness", "negative", "taglish"),
    ("d man lng ako tnulungan nung clerk, nkkainis", "staff_responsiveness", "negative", "tl"),
    ("Rude ng guard today, ang sungit niya sa mga students.", "staff_responsiveness", "negative", "taglish"),
    ("The staff did not even greet us and kept chatting among themselves.", "staff_responsiveness", "negative", "en"),
    # =====================================================================
    # staff_responsiveness / positive
    # =====================================================================
    ("Ang bait nung staff sa registrar. Tinulungan ako step by step.", "staff_responsiveness", "positive", "taglish"),
    ("The cashier was polite, patient, and very helpful.", "staff_responsiveness", "positive", "en"),
    ("Magalang at accommodating yung librarian. Salamat po.", "staff_responsiveness", "positive", "taglish"),
    ("OSAS staff answered all my questions with a smile.", "staff_responsiveness", "positive", "en"),
    ("Approachable yung admissions officer. I felt welcome.", "staff_responsiveness", "positive", "taglish"),
    ("They went out of their way to find my record. Excellent service.", "staff_responsiveness", "positive", "en"),
    ("Mabait at mabilis tumugon yung personnel. Very professional.", "staff_responsiveness", "positive", "taglish"),
    ("Kind staff at the window. They treated students with respect.", "staff_responsiveness", "positive", "en"),
    ("Thank you sa guard, magalang magpa-pila.", "staff_responsiveness", "positive", "taglish"),
    ("Helpful and friendly employees at student affairs.", "staff_responsiveness", "positive", "en"),
    # new
    ("Hindi naman bastos yung staff, actually sobrang bait pa nga.", "staff_responsiveness", "positive", "taglish"),
    ("Very accommodating yung clerk, tinuruan niya ako kung paano mag-fill out ng form.", "staff_responsiveness", "positive", "taglish"),
    ("Thank u po sa staff ng registrar, ang bait nila 😊", "staff_responsiveness", "positive", "taglish"),
    ("The guard was respectful and guided us to the right window.", "staff_responsiveness", "positive", "en"),
    # =====================================================================
    # staff_responsiveness / constructive
    # =====================================================================
    ("The clerk was dismissive when I asked a question. Staff should be trained to be more patient.", "staff_responsiveness", "constructive", "en"),
    ("Nobody was at the desk for a long time; they should assign someone to cover lunch breaks.", "staff_responsiveness", "constructive", "en"),
    ("Staff kept looking at their phones. Please remind them to attend to students first.", "staff_responsiveness", "constructive", "en"),
    ("The front desk did not return my calls. It would be better to have a dedicated person for inquiries.", "staff_responsiveness", "constructive", "en"),
    ("Some employees are rude to students; customer service training would help.", "staff_responsiveness", "constructive", "en"),
    ("Masungit yung staff sa window, sana turuan silang makipag-usap nang maayos sa mga estudyante.", "staff_responsiveness", "constructive", "tl"),
    ("Walang sumasagot sa information desk, dapat may naka-assign na tao kahit lunch break.", "staff_responsiveness", "constructive", "tl"),
    ("Hindi ako pinansin ng personnel kahit ako na yung susunod, sana mas maging magalang sila.", "staff_responsiveness", "constructive", "tl"),
    ("Bastos magsalita yung guard, dapat may seminar sa tamang pakikitungo sa mga estudyante.", "staff_responsiveness", "constructive", "tl"),
    ("Yung staff hindi helpful, sana mag-undergo sila ng customer service training.", "staff_responsiveness", "constructive", "taglish"),
    ("Walang tao sa desk pag lunch, please assign someone para may mag-assist sa students.", "staff_responsiveness", "constructive", "taglish"),
    ("Ang init ng ulo ng clerk sa window 2, they should be more patient with first-year students.", "staff_responsiveness", "constructive", "taglish"),
    ("Hindi sumasagot yung staff sa email, mas okay kung may designated person na magrereply.", "staff_responsiveness", "constructive", "taglish"),
    ("The staff are kind pero iisa lang yung naka-duty, hopefully magdagdag pa sila ng tao.", "staff_responsiveness", "constructive", "taglish"),
    ("Rude yung guard sa pila, sana i-remind sila na maging respectful sa students.", "staff_responsiveness", "constructive", "taglish"),
    ("Walang gumabay sa akin sa window, suggest ko na may help desk na marunong sumagot.", "staff_responsiveness", "constructive", "taglish"),
    # =====================================================================
    # communication_clarity / negative
    # =====================================================================
    ("Hindi clear yung requirements. Confusing yung notices sa wall.", "communication_clarity", "negative", "taglish"),
    ("The instructions for enrollment are unclear and contradictory.", "communication_clarity", "negative", "en"),
    ("Malabo yung announcement. Hindi ko alam kung anong form gagamitin.", "communication_clarity", "negative", "tl"),
    ("Nobody explained the deadline. I missed it because of poor communication.", "communication_clarity", "negative", "en"),
    ("Yung Facebook post different sa poster. Magulo yung information.", "communication_clarity", "negative", "taglish"),
    ("Signs are outdated. Students get the wrong list of documents.", "communication_clarity", "negative", "en"),
    ("Hindi naiintindihan yung procedure. Walang FAQ na madaling basahin.", "communication_clarity", "negative", "taglish"),
    ("They use jargon and never clarify steps for first-year students.", "communication_clarity", "negative", "en"),
    ("Walang proper orientation. Confusing lahat ng steps.", "communication_clarity", "negative", "taglish"),
    ("Email replies are vague. Still do not know what to submit.", "communication_clarity", "negative", "en"),
    ("Di clear kung kailan yung deadline ng payment.", "communication_clarity", "negative", "taglish"),
    ("Announcement came too late and the details were incomplete.", "communication_clarity", "negative", "en"),
    # new
    ("Hindi malinaw yung instructions sa form.", "communication_clarity", "negative", "tl"),
    ("Di ko gets yung announcement, ang gulo ng details sa post nila.", "communication_clarity", "negative", "taglish"),
    ("The notice says one thing and the staff says another. Very confusing.", "communication_clarity", "negative", "en"),
    ("Walang nakalagay kung anong requirements, nalito lahat ng estudyante.", "communication_clarity", "negative", "tl"),
    # =====================================================================
    # communication_clarity / positive
    # =====================================================================
    ("Clear yung instructions sa bulletin. Madaling sundan.", "communication_clarity", "positive", "taglish"),
    ("The office posted a simple step-by-step guide. Very clear.", "communication_clarity", "positive", "en"),
    ("May FAQ na updated. Naintindihan ko agad yung requirements.", "communication_clarity", "positive", "taglish"),
    ("Deadlines were announced early and explained well.", "communication_clarity", "positive", "en"),
    ("Maayos yung signage. Hindi na ako nalito.", "communication_clarity", "positive", "tl"),
    ("Staff explained the process in both Filipino and English. Clear communication.", "communication_clarity", "positive", "en"),
    ("Yung orientation helpful. All procedures were listed.", "communication_clarity", "positive", "taglish"),
    ("Website notice matches what the office told me. Consistent info.", "communication_clarity", "positive", "en"),
    # new
    ("Di naman magulo yung instructions, madali lang sundan.", "communication_clarity", "positive", "taglish"),
    ("Clear na clear yung announcement, may date and requirements pa.", "communication_clarity", "positive", "taglish"),
    ("The poster was simple and easy to understand.", "communication_clarity", "positive", "en"),
    ("Maganda yung step-by-step guide sa website, naintindihan ko agad.", "communication_clarity", "positive", "taglish"),
    # =====================================================================
    # communication_clarity / constructive
    # =====================================================================
    ("The requirements are confusing; please post a clear checklist at the entrance.", "communication_clarity", "constructive", "en"),
    ("The Facebook post and the poster say different things. They should update both to match.", "communication_clarity", "constructive", "en"),
    ("Deadlines were not announced early. Hopefully they can send reminders a week before.", "communication_clarity", "constructive", "en"),
    ("Instructions for enrollment are unclear. A step-by-step guide would help first-year students.", "communication_clarity", "constructive", "en"),
    ("The email reply was vague; it should list exactly which documents to submit.", "communication_clarity", "constructive", "en"),
    ("Magulo yung announcement, sana ilagay nang malinaw sa bulletin board ang mga requirements.", "communication_clarity", "constructive", "tl"),
    ("Hindi malinaw kung kailan ang deadline, dapat may paalala bago matapos ang petsa.", "communication_clarity", "constructive", "tl"),
    ("Iba yung nakasulat sa poster at sa Facebook, sana pareho na lang ang impormasyon.", "communication_clarity", "constructive", "tl"),
    ("Nalito ako sa mga hakbang, mas mabuti kung may nakasulat na gabay sa bawat bintana.", "communication_clarity", "constructive", "tl"),
    ("Hindi clear yung requirements, sana gumawa sila ng simple checklist.", "communication_clarity", "constructive", "taglish"),
    ("Confusing yung procedure sa enrollment, please add a step-by-step guide sa website.", "communication_clarity", "constructive", "taglish"),
    ("Outdated yung signage, dapat i-update para hindi na malito ang students.", "communication_clarity", "constructive", "taglish"),
    ("Di ko alam kung anong form ang kukunin, mas okay kung may FAQ na madaling basahin.", "communication_clarity", "constructive", "taglish"),
    ("Late na na-announce yung deadline, hopefully mag-post sila ng reminders nang mas maaga.", "communication_clarity", "constructive", "taglish"),
    ("Vague yung sagot nila sa email, sana specific na ilista yung documents na kailangan.", "communication_clarity", "constructive", "taglish"),
    # =====================================================================
    # service_accessibility / negative
    # =====================================================================
    ("Office is always closed when I am free after class. Limited hours.", "service_accessibility", "negative", "en"),
    ("Sarado na pagdating ko ng 4pm. Hindi accessible sa working students.", "service_accessibility", "negative", "taglish"),
    ("No online appointment. I have to go to campus just to ask one question.", "service_accessibility", "negative", "en"),
    ("Walang online channel. Mahirap i-contact yung office.", "service_accessibility", "negative", "taglish"),
    ("They only serve until lunch on Fridays. Very limited access.", "service_accessibility", "negative", "en"),
    ("Hindi available yung service sa evening. Working student ako.", "service_accessibility", "negative", "taglish"),
    ("Phone is never answered. Impossible to reach the unit.", "service_accessibility", "negative", "en"),
    ("Walang weekend window during enrollment. Inaccessible.", "service_accessibility", "negative", "taglish"),
    ("The office is hard to find and there is no directory.", "service_accessibility", "negative", "en"),
    ("Limited slots lang. Hindi ako naka-avail ng appointment.", "service_accessibility", "negative", "taglish"),
    # new
    ("Hindi accessible yung office, laging sarado pag free time ko.", "service_accessibility", "negative", "taglish"),
    ("Walang paraan para mag-email o mag-message, kailangan pang pumunta personally.", "service_accessibility", "negative", "taglish"),
    ("The office closes at noon on Saturdays, impossible for working students.", "service_accessibility", "negative", "en"),
    ("wla na slots, pahirapan mag-book ng appointment", "service_accessibility", "negative", "taglish"),
    # =====================================================================
    # service_accessibility / positive
    # =====================================================================
    ("They extended hours during enrollment. Very accessible.", "service_accessibility", "positive", "en"),
    ("May online request na. Hindi na kailangan pumila palagi.", "service_accessibility", "positive", "taglish"),
    ("Saturday window helped working students. Thank you.", "service_accessibility", "positive", "en"),
    ("Madaling i-contact via email. They reply the same day.", "service_accessibility", "positive", "taglish"),
    ("Clear office hours posted and they actually follow them.", "service_accessibility", "positive", "en"),
    ("May ticketing system. Accessible kahit peak season.", "service_accessibility", "positive", "taglish"),
    ("I booked an appointment online and it was honored. Convenient.", "service_accessibility", "positive", "en"),
    ("Open sila hanggang 6pm this week. Helpful for late classes.", "service_accessibility", "positive", "taglish"),
    # new
    ("Open na sila ng Saturday, malaking tulong sa working students.", "service_accessibility", "positive", "taglish"),
    ("Hindi na kailangan pumunta sa campus, online na lahat ng request.", "service_accessibility", "positive", "taglish"),
    ("Mabilis sumagot sa Facebook page nila, super accessible.", "service_accessibility", "positive", "taglish"),
    ("The new online booking made it very easy to schedule my visit.", "service_accessibility", "positive", "en"),
    # =====================================================================
    # service_accessibility / constructive
    # =====================================================================
    ("The office closes before I finish class; please extend hours for working students.", "service_accessibility", "constructive", "en"),
    ("There is no online appointment option. They should add one so we do not have to come to campus for one question.", "service_accessibility", "constructive", "en"),
    ("The unit is hard to find. Maybe put up a directory or signs near the entrance.", "service_accessibility", "constructive", "en"),
    ("Nobody answers the phone; it would help to have an official email or chat support.", "service_accessibility", "constructive", "en"),
    ("Sarado na ang opisina pagdating ko galing klase, sana palawigin ang oras para sa mga working student.", "service_accessibility", "constructive", "tl"),
    ("Walang online na paraan para mag-request, dapat magkaroon para hindi na kami pumupunta pa sa campus.", "service_accessibility", "constructive", "tl"),
    ("Mahirap hanapin yung opisina, sana lagyan ng malinaw na karatula sa pasukan.", "service_accessibility", "constructive", "tl"),
    ("Hindi sinasagot ang telepono, mas mainam kung may email na mabilis sumagot.", "service_accessibility", "constructive", "tl"),
    ("Hanggang 4pm lang bukas yung office, sana mag-extend sila ng hours para sa working students.", "service_accessibility", "constructive", "taglish"),
    ("Walang online appointment, suggest ko na mag-add sila ng booking system.", "service_accessibility", "constructive", "taglish"),
    ("Limited slots lang per day, hopefully dagdagan nila yung slots pag enrollment.", "service_accessibility", "constructive", "taglish"),
    ("Hindi ko mahanap yung office, sana magkaroon ng directory sa lobby.", "service_accessibility", "constructive", "taglish"),
    ("Walang weekend window, please open Saturdays para sa mga hindi makapunta ng weekdays.", "service_accessibility", "constructive", "taglish"),
    ("Hindi sinasagot yung phone, mas okay kung may Facebook page na active para makapag-message kami.", "service_accessibility", "constructive", "taglish"),
    # =====================================================================
    # facility_conditions / negative
    # =====================================================================
    ("Yung CR sa registrar area madumi at sira yung lock.", "facility_conditions", "negative", "tl"),
    ("Waiting area has broken chairs and no ventilation. Uncomfortable.", "facility_conditions", "negative", "en"),
    ("Maamoy at madumi yung comfort room.", "facility_conditions", "negative", "taglish"),
    ("The hallway is dark and leaking. Poor facility maintenance.", "facility_conditions", "negative", "en"),
    ("Walang aircon, mainit sa pila. Students are standing for hours.", "facility_conditions", "negative", "taglish"),
    ("Restroom has no soap and the faucet is broken.", "facility_conditions", "negative", "en"),
    ("Sira sira yung ceiling sa waiting area. Nakakatakot umupo.", "facility_conditions", "negative", "taglish"),
    ("Trash is not collected. The lobby looks neglected.", "facility_conditions", "negative", "en"),
    ("Baha sa hallway pag umuulan. Unsafe facility.", "facility_conditions", "negative", "taglish"),
    ("Lights flicker in the library annex. Needs immediate repair.", "facility_conditions", "negative", "en"),
    ("Ang dumi ng CR sa second floor. Walang tissue, walang water.", "facility_conditions", "negative", "taglish"),
    ("Waiting benches are damaged and some are missing.", "facility_conditions", "negative", "en"),
    # new
    ("Ang init sa loob ng waiting area, walang bentilador.", "facility_conditions", "negative", "tl"),
    ("The restroom smells terrible and the door will not lock.", "facility_conditions", "negative", "en"),
    ("Madumi talaga yung CR, grabe di na malinis.", "facility_conditions", "negative", "taglish"),
    ("Basag yung bintana at tumutulo pag umuulan sa registrar.", "facility_conditions", "negative", "tl"),
    # =====================================================================
    # facility_conditions / positive
    # =====================================================================
    ("Malinis yung CR and waiting area. Nice environment.", "facility_conditions", "positive", "taglish"),
    ("The lobby was recently painted and chairs were replaced. Clean.", "facility_conditions", "positive", "en"),
    ("May bagong electric fan sa pila. Mas komportable na.", "facility_conditions", "positive", "taglish"),
    ("Restrooms are maintained and smell clean. Good job facilities.", "facility_conditions", "positive", "en"),
    ("Maayos yung lighting sa hallway. Safe to walk.", "facility_conditions", "positive", "taglish"),
    ("Library study area is tidy and well kept.", "facility_conditions", "positive", "en"),
    ("Na-fix na yung leak. Salamat sa maintenance team.", "facility_conditions", "positive", "taglish"),
    ("Comfortable seating and a clean floor in the cashier lounge.", "facility_conditions", "positive", "en"),
    # new
    ("Hindi na mainit sa waiting area, may aircon na.", "facility_conditions", "positive", "taglish"),
    ("The new benches are comfortable and the area is clean.", "facility_conditions", "positive", "en"),
    ("Ang linis na ng CR ngayon, salamat sa maintenance 👍", "facility_conditions", "positive", "taglish"),
    ("Maliwanag at maayos na yung hallway, safe na maglakad.", "facility_conditions", "positive", "taglish"),
    # =====================================================================
    # facility_conditions / constructive
    # =====================================================================
    ("The restroom has no soap and a broken faucet. Please fix it and restock supplies regularly.", "facility_conditions", "constructive", "en"),
    ("The waiting area is very hot; installing fans or aircon would help.", "facility_conditions", "constructive", "en"),
    ("The hallway leaks when it rains. The roof should be repaired before the next semester.", "facility_conditions", "constructive", "en"),
    ("Many chairs in the lobby are broken. Please replace them.", "facility_conditions", "constructive", "en"),
    ("Lights in the library annex keep flickering; maintenance should check the wiring.", "facility_conditions", "constructive", "en"),
    ("Madumi ang CR at sira ang lock, sana linisin at ayusin ito araw-araw.", "facility_conditions", "constructive", "tl"),
    ("Napakainit sa pila, dapat magkabit ng bentilador o aircon sa waiting area.", "facility_conditions", "constructive", "tl"),
    ("Tumutulo ang kisame kapag umuulan, sana maayos na bago magsimula ang susunod na semester.", "facility_conditions", "constructive", "tl"),
    ("Sira na ang mga upuan sa labas ng cashier, dapat palitan na ang mga ito.", "facility_conditions", "constructive", "tl"),
    ("Madumi yung CR sa second floor, sana may schedule ng paglilinis every hour.", "facility_conditions", "constructive", "taglish"),
    ("Mainit sa waiting area, please add electric fans para hindi na kami pinagpapawisan sa pila.", "facility_conditions", "constructive", "taglish"),
    ("Sira yung ceiling sa hallway, they should repair it bago pa may masaktan.", "facility_conditions", "constructive", "taglish"),
    ("Walang tissue at sabon sa restroom, mas okay kung may regular na restocking.", "facility_conditions", "constructive", "taglish"),
    ("Madilim yung hallway pag gabi, hopefully mag-install sila ng mas maliwanag na lights.", "facility_conditions", "constructive", "taglish"),
    ("Kulang yung upuan sa waiting area, sana dagdagan yung benches.", "facility_conditions", "constructive", "taglish"),
    # =====================================================================
    # generic comments, no specific facet (aspect = "")
    # =====================================================================
    ("Very good service overall. Thank you!", "", "positive", "en"),
    ("Maganda po ang serbisyo, salamat.", "", "positive", "tl"),
    ("Ang galing nila, satisfied ako sa experience ko dito.", "", "positive", "taglish"),
    ("Poor service overall. Not satisfied at all.", "", "negative", "en"),
    ("Hindi maganda ang serbisyo, nakakadismaya.", "", "negative", "tl"),
    ("Bad experience talaga, hindi na ako babalik dito.", "", "negative", "taglish"),
    ("The service needs to improve; please do better next time.", "", "constructive", "en"),
    ("Sana mas pagbutihin pa ang serbisyo para sa mga estudyante.", "", "constructive", "tl"),
    ("Hindi maganda yung experience ko, sana ma-improve nila lahat ng process.", "", "constructive", "taglish"),
]


def all_examples() -> list[tuple[str, str, str, str]]:
    return list(EXAMPLES)


def validate_examples() -> list[str]:
    """Return a list of problems (empty list = seed is clean).

    Catches typos in labels, duplicate texts, and the labeling-rule
    violation that hurts the constructive class most: suggestion words
    inside rows that are not constructive.
    """
    # imported here so the seed stays importable without the feature module
    from ml.features import has_suggestion_cue

    problems: list[str] = []
    seen: dict[str, int] = {}
    for i, (text, aspect, sentiment, lang) in enumerate(EXAMPLES):
        if aspect != "" and aspect not in ASPECTS:
            problems.append(f"row {i}: unknown aspect {aspect!r}")
        if sentiment not in SENTIMENTS:
            problems.append(f"row {i}: unknown sentiment {sentiment!r}")
        if lang not in LANGUAGES:
            problems.append(f"row {i}: unknown language {lang!r}")
        key = text.strip().lower()
        if key in seen:
            problems.append(f"row {i}: duplicate of row {seen[key]}: {text!r}")
        seen[key] = i
        if sentiment != "constructive" and has_suggestion_cue(text):
            problems.append(f"row {i}: {sentiment} row contains a suggestion cue: {text!r}")
        if sentiment == "constructive" and not has_suggestion_cue(text):
            problems.append(f"row {i}: constructive row has no suggestion cue: {text!r}")
    return problems
