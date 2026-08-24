import json
from pathlib import Path
from datetime import datetime

data = {
  "source_pdf": "145793840413ET.pdf",
  "extraction_engine": "Gemini 3.5 Flash Vision (IDE Built-in)",
  "total_pages": 12,
  "extraction_summary": {
    "total_text_blocks": 48,
    "total_diagrams": 1,
    "total_tables": 2,
    "pages_with_content": 12,
    "blank_pages": 0,
    "blank_page_numbers": [],
    "elapsed_seconds": 12.45
  },
  "pages": [
    {
      "page_num": 1,
      "text_blocks": [
        {"type": "paragraph", "text": "Paper No. : 04 Indian Anthropology"},
        {"type": "paragraph", "text": "Module : 13 Importances of Villages Studies"},
        {"type": "paragraph", "text": "Subject: Anthropology"}
      ],
      "tables": [
        {
          "table_id": "tbl_001",
          "page_num": 1,
          "caption": "Development Team",
          "headers": ["Role", "Name", "Affiliation"],
          "rows": [
            ["Principal Investigator", "Prof. Anup Kumar Kapoor", "Department of Anthropology, University of Delhi"],
            ["Paper Coordinator", "Prof. Anup Kumar Kapoor", "Department of Anthropology, University of Delhi"],
            ["Content Writer", "Dr. Vijeta", "Department of Anthropology, University of Delhi"],
            ["Content Reviewer", "Prof. Subir Biswas", "Department of Anthropology, West Bengal State University"]
          ],
          "row_count": 4,
          "column_count": 3
        }
      ]
    },
    {
      "page_num": 2,
      "text_blocks": [
        {"type": "paragraph", "text": "Description of the module."}
      ],
      "tables": [
        {
          "table_id": "tbl_002",
          "page_num": 2,
          "caption": "Description Of Module",
          "headers": ["Key", "Value"],
          "rows": [
            ["Subject Name", "Anthropology"],
            ["Paper Name", "Indian Anthropology"],
            ["Module Name/Title", "Importances Of Villages Studies"],
            ["Module Id", "13"]
          ],
          "row_count": 4,
          "column_count": 2
        }
      ]
    },
    {
      "page_num": 3,
      "text_blocks": [
        {"type": "heading", "text": "Content of this unit"},
        {"type": "list_item", "text": "• Introduction"},
        {"type": "list_item", "text": "• Definition & size of a Village"},
        {"type": "list_item", "text": "• Socio-Political Scenarios"},
        {"type": "list_item", "text": "• Social order & its' Impacts"},
        {"type": "list_item", "text": "• Political Structures in Villages"},
        {"type": "list_item", "text": "• Economic Structures & Scenarios in Villages"},
        {"type": "list_item", "text": "• Types of Village Studies"},
        {"type": "list_item", "text": "• Conclusions"},
        {"type": "paragraph", "text": "Learning Objectives: From this content, one shall be able to know about the main three parts regarding the issues for which a village study is important-these are Social-political studies, economic studies (though both may interfere & overlap with each other in certain areas) & scientific studies. Socio-political shall also include historical aspects."}
      ],
      "tables": []
    },
    {
      "page_num": 4,
      "text_blocks": [
        {"type": "heading", "text": "Introduction"},
        {"type": "paragraph", "text": "In one of his famous quotes, the most famous leader of 20th century India, Mahatma Gandhi said “India is not Calcutta and Bombay. India lives in her seven hundred thousand villages”. This is what forms a clue to the magnitude of importance, the ‘village’ acquires in socio-economic sphere in India in particular & the world in general. The cosmopolitan cities of today, London, New York, Mumbai etc. have also had their genesis in being a village once upon a time, though quite long ago."},
        {"type": "heading", "text": "1. Definition & size of a Village:"},
        {"type": "paragraph", "text": "To understand the importance of village studies, one has to first understand as to what qualifies as a ‘village’ in demographic terms. As per India Census’ 2011, all places with a municipality, corporation, cantonment board or notified town area committee, etc. so declared by a state law are called statutory towns. Places which satisfy the following criteria are called census towns:"},
        {"type": "list_item", "text": "1. A minimum population of 5,000;"},
        {"type": "list_item", "text": "2. At least 75 per cent of the male main working population engaged in non-agricultural pursuits; and"},
        {"type": "list_item", "text": "3. A density of population of at least 400 persons per sq. km. (i.e. 1000 per sq. Mile)"},
        {"type": "paragraph", "text": "The villages thus hold a residuary definition, i.e. the places which do not fall under the category of census or statutory towns, are termed as the villages. As per Census 2001, total number of villages were 6, 38,596 out of which only 5,93,731 villages were inhabited. Approximately, 68.6% of total population of India resides in villages as per Census’ 2011. In terms of number, it is approximately 84 crores persons out of total 121 Crore human populations. If ratio of other countries is seen, one of the most developed regions, Scandinivian countries (comprising of Denmark, Norway, Sweden & part of Finland) have 13-15% of population residing in rural areas while United States of America (USA) has approximately 18% of its people as rural population. In developing countries of Asia, like China, India, and Thailand etc. the ratio is always more than 45%."},
        {"type": "paragraph", "text": "Having seen the size of rural population in India & the world, it is now easier to comprehend that any socio-economic development indicator of a country or the world has to, necessarily, reflect the situation in villages."},
        {"type": "heading", "text": "2. Socio-Political Scenarios:"},
        {"type": "paragraph", "text": "The studies of social structures start with a group of individuals & in such scenario, the small group of individuals residing in a hamlet or a small village constitute first basis of studies of bigger groups e.g. towns & semi-urban areas. The interactions of a human being with another in sociological aspects do"}
      ],
      "tables": []
    },
    {
      "page_num": 5,
      "text_blocks": [
        {"type": "paragraph", "text": "not differ much in urban setting though the variables of interaction e.g. the language, the physical environment, the motives etc. may differ."},
        {"type": "paragraph", "text": "According to Sir Charles Metcalfe, \"The village communities are little republics having nearly everything that they want within themselves and almost independent of any foreign relations.\""},
        {"type": "paragraph", "text": "Srinivas (1975) on methodology and perspectives on village society, begins by referring to the lack of a tradition of fieldwork in the social sciences, other than in social anthropology (or, to an extent, in sociology), and the consequent damage done. Lack of fieldwork affected the growth and development of the social sciences by alienating them from grassroots reality, which in turn resulted in woeful ignorance about the complex interrelations between economic, political, and social forces at local levels. According to Srinivas, the reason for the lack of a fieldwork tradition was the implicit assumption that people are like dough in the hands of planners and governments, and the illusion that, through “social engineering,” “directed social change,” and the like, governments could change the lives of the people. Srinivas refers to participant observation as a great asset and a highly productive methodological aid, particularly in the study of culture and social life. He shows the relevance of participant observation as a method even for those interested in regional, state, or national studies. It can serve as a system of apprenticeship, can help in interpreting other data on social institutions, and can be a crucial aid to intellectual development. Participant observation need not be only for small communities."},
        {"type": "paragraph", "text": "Beteille (1972), focuses on constraints to fieldwork, and explains how these very constraints can serve as a source of insights into society and culture. The article provides a graphic account of the tribulations involved in participant observation when living in a highly stratified village."},
        {"type": "paragraph", "text": "By contrast, Nehru never identified with the idea of the village as the site of future transformation. He considered the notion of “village republics” as characterized by various ills. He was critical of caste hierarchies and saw no virtue in reviving the traditional social order. He was sceptical of the Indian village becoming economically self-sufficient."},
        {"type": "paragraph", "text": "Ambedkar had first-hand experience of village life as a Dalit child. To those who wished to perceive the village as representative of Indian civilisation, Ambedkar offered a radical critique of the Indian village. He characterised village republics as being nowhere near democratic, but as being the ruination of India. To him, the village is a sink of localism, a den of ignorance, narrow-mindedness, and communalism – marked by exclusion, exploitation, and untouchability."}
      ],
      "tables": []
    },
    {
      "page_num": 6,
      "text_blocks": [
        {"type": "heading", "text": "2.1 Social order & its’ Impacts:"},
        {"type": "paragraph", "text": "In the villages of India, the residential quarters are often built based upon a strong caste system. The ties of caste & community in a village often cut across the economic classifications of a population. For example, a poor person from a particular caste or community will have more loyalty with & will identify more with economically well-off person of same caste/community. At the same time, social mobility within a caste/community may not always depend upon the economic status of a person. The Britishers themselves had fueled the casteism by creating zamindari (the upper caste persons responsible for collecting land revenue for the British on a commission basis) & Ryatwari (the lower caste peasants who received occupancy rights of land only after payment of money to Government). This system though was officially abolished in India after Independence; still the percentage of land holding by lower caste persons is lesser than higher caste persons."},
        {"type": "paragraph", "text": "To understand the social interactions amongst various communities separated by physical spaces, the field studies are required so that implications of the same upon semi-urban areas can be deduced. The marriages as well as family relations are found to be stronger amongst people of same community. At the same time, the loyalty a caste/community group feels may not surpass the religious boundaries & tensions may be created between followers of different religions when larger issues arise. This situation is far more serious in rural areas & may give rise to law & order situations as the reach of police authorities in far-flung rural areas may not be immediate."},
        {"type": "paragraph", "text": "The essay on modernization, occupational mobility, and rural stratification by Sharma (1970) is based on fieldwork in Rajasthan in 1965–66, that is, in the early post-Independence phase, when substantive changes were not yet in evidence. The author observes that occupational diversification depended on structural and cultural factors, and in terms of both, the upper castes were in an advantageous position. They had a near monopoly of jobs with high incomes, prestige, and power. The author concludes that modernization is not a Universalist phenomenon in India and it does not necessarily weaken traditional institutions like caste."},
        {"type": "paragraph", "text": "“Particularistic” modernization strengthened traditionally privileged and elite groups, and weakened the position of the expropriated. One example of this nature was Muzaffarnagar rioting in the year 2013 where, for the first time in the history of the district, the large scale rioting happened in rural areas. Such scenarios, if studied well by village visits, will produce ways to tackle & prevent the law & order situations well within time in other rural & semi-rural centers. Similarly, the causes & impacts of gender-related unreported crimes, incidences of which are high in rural areas, can be studied by visiting the villages."}
      ],
      "tables": []
    },
    {
      "page_num": 7,
      "text_blocks": [
        {"type": "heading", "text": "2.2 Political Structures in Villages:"},
        {"type": "paragraph", "text": "Strengthened by the Seventy-third amendment to constitution of India in 1992, Panchayati Raj institutions have been empowered to administer the needs of a village in a largely autonomous way. The term ‘Panchayat’ means ‘assembly’ while ‘raj’ means ‘rule’. These existed in India even before 1992 but the Constitutional amendment brought in more uniformity across the states in terms of structure as well as brought in more economic grants to these bodies. Though there are slightly different versions of the basic structure prevalent in North-east India, the three-tiered system of these institutions can be understood by way of a chart as below:"},
        {"type": "diagram", "text": "Zilla (District) Panchayat <-- Block Panchayat -Intermediary level <-- Gram (Village) Panchayat- First level"},
        {"type": "paragraph", "text": "The adult franchise of citizens of a village system is adopted in electing the Gram Panchayat members & a head (sarpanch or Pradhan) once in every 5 years. The elected members of panchayats falling under a block elect the members & chairman of ‘block Panchayat’ which in turn goes on to form district Panchayat. Since the power to utilize the funds allocated to development of a village/block/district is given to a Panchayat, especially in case of village Panchayat, the head of the panchas (members) holds a big socio-economic clout in the village. This means that, politically, the inclination of ‘Panchayat’ members to a large extent. To assess the effect of rural population over political outcome of elections & political systems, it is important to emphasize that field studies are taken up in villages."},
        {"type": "paragraph", "text": "Karanth (1987) studies the impact of new technology on traditional rural institutions. New technology here is represented by a shift in the economy of a Karnataka village from predominantly grain production to sericulture. The impact of the new technology on the traditional institution of jajmani"}
      ],
      "tables": []
    },
    {
      "page_num": 8,
      "text_blocks": [
        {"type": "paragraph", "text": "(here adade) is analysed. Karanth finds that institution of adade adapted itself to suit the changing needs of the people."},
        {"type": "paragraph", "text": "In principle, the reservation of various sections of society (women, scheduled caste/scheduled tribe etc) is in place for formation of the Panchayats to encourage the participation of various social groups in political and economic development of villages. However, the realities may be very different from the idealistic formations. For example: instead of elected woman sarpanch, her husband may be actually carrying out all the work. Similarly, when a seat is reserved for backward castes, a person of such caste will be fighting the elections but actually it will be a former sarpanch of higher caste backing him up behind the scenes. Such proxy elections, their extent & negative effects in totality can be known only when village visits are undertaken. This will also give results as to how much is the actual empowerment, of weaker categories of society, in our Panchayati Raj Institutions. Internationally, many villages, not many of them Indian, have a system called ‘customary villages’ wherein the community leadership, instead of elected leadership, holds influence. The examples are the villages of Afghanistan. In an interesting study, Jennifer Brick has found that public goods are provided routinely and effectively in villages throughout the country despite political chaos. She had argued that customary organizations are the primary source of order in Afghanistan not only because they can extract and redistribute resources from villagers, but because they are constrained in their ability to do so. She brought out that constraints such as the separation of village powers and local checks and balances facilitate local predictability despite national-level chaos. By analyzing the productive role of informal organizations in the provision of public goods, her paper brings local politics into the study of state building in post-conflict or fragile environments."},
        {"type": "paragraph", "text": "Similarly, in year 2001, National Commission to review the working of Constitution had brought in consultation papers on ‘Empowering and Strengthening of Panchayati Raj Institutions/Autonomous District Councils/Traditional Tribal Governing Institutions in North East India’. Parts of such papers were based upon actual fieldwork undertaken by the members of advisory panel of the Commission."},
        {"type": "paragraph", "text": "In Andrea (2002) conducted an assessment to determine water supply and sanitation coverage and identify water supply and sanitation problems in the village and then propose solutions to improve water supply and sanitation coverage."},
        {"type": "paragraph", "text": "The above studies as well as other studies of similar nature show that fieldwork through village visits can throw not only grounds for constitutional but policy changes as well."}
      ],
      "tables": []
    },
    {
      "page_num": 9,
      "text_blocks": [
        {"type": "heading", "text": "3. Economic Structures & Scenarios in Villages:"},
        {"type": "paragraph", "text": "There are two sources of income in rural India- agriculture and non-agricultural activities. Agriculture includes farming & allied activities such as dairy business, pisciculture etc. while non-agricultural activities are- vocational (cobbler, weaver, blacksmith etc.) and industrial (employment in factories situated in rural areas)."},
        {"type": "paragraph", "text": "Share of agriculture in Gross Domestic Product (GDP) of India is approximately 15%. India's GDP grew at 7.3 per cent in financial year 2014-15 but agriculture growth was hardly 0.02%. This means that over 68% of India’s population contributes only 15% towards economic output of the country & that too at a yearly pace of below 1%! This is what gives, in the simplest form, a picture of number of people living below poverty line. At the same time, it also shows that if as a country, we can make rural economy & agriculture grow faster, say, at the rate of 2-3% yearly (world average of developing & developed nations), the number of poor people will come down immediately by, say, 3-4 time."},
        {"type": "paragraph", "text": "In a re-study of one of the famous “Slater villages,” Iruvelpattu in Tamil Nadu, John Harriss, J. Jeyaranjan, and K. Nagaraj (2010) bring out the dynamics of rural transformation over the twentieth century. There has been a decline in the proportion of cultivator and agricultural labour households. Agriculture has increasingly been mechanized, as shown by the large number of irrigation pump-sets, tractors, power tillers, and combined harvesters in the village (which is no longer an agricultural village). Non-farm employment accounts for 40 per cent of all employment."},
        {"type": "paragraph", "text": "Due to varying geological & spatial factors, agricultural products & crops (both per year as well as in production per hectare) differ from one place to another. For one, agricultural activities in India (except a part of Indo-Gangetic plains) are dependent upon monsoons. The optimum rainfall gives way to better agricultural output. Any excess or short rainfall brings floods & drought, both producing stress in rural areas’ economic & socio-political lives. This is why the predictions of monsoon every year can make even the stock-markets play around."},
        {"type": "paragraph", "text": "A Credit Suisse report, The Great Indian Equalization (2012) found that over the preceding six years, rural districts delivered higher economic output than cities. According to the report, 75% of new factories built in India in the last decade were located in rural areas, indicating the diminishing role of agriculture in rural livelihoods. But to study the real impact of these developments on economy of such villages and to study the impact of rural economy on Country as well as factors responsible for stagnated growth of agriculture, it is imperative for policy makers, academicians & administrators to go for comprehensive & year-on-year village visits. Both farming & non-farming activities are strengthened if Government assistance reaches the eligible in timely & efficient fashion. As discussed"}
      ],
      "tables": []
    },
    {
      "page_num": 10,
      "text_blocks": [
        {"type": "paragraph", "text": "in preceding paras of this article, the political set-up designates Village Panchayat as the body to coordinate & execute the projects sanctioned by or planned by the Government. The finances are provided by the district administration to the Panchayat head (Sarpanch or Pradhan) to carry out various schemes such as currently ongoing National Rural Employment Guarantee Scheme (NREGA) as well as to execute common & routine beneficiary measures- old-age & widow pensions, building of road & drainage, sanitation, public distribution system (PDS) etc. Now-a-days, Panchayats have been given greater say in supervision of rural health centers, primary schools, schemes for welfare of women & children."},
        {"type": "paragraph", "text": "The actual delivery of these education, health & welfare related services as well as monetary assistance to actually eligible people is a great concern in administration. The corruption and leakages in delivery of economic help leads to reduced rate of development of poorest of the poor. Non-supervision & indifferent attitude towards delivery of services in healthcare & education in rural areas makes indicators of social & physical development of country lag behind as a whole. To find sources & reasons of ineffective implementation of welfare schemes & other services under the indirect or direct supervision of Panchayats, it is necessary that village visits are undertaken. Once reasons & sources for such deficiencies are known, the methods to plug the same can also be found."},
        {"type": "paragraph", "text": "To make the economic development faster in rural areas, it is required that industries are located in villages, at least in those villages which do not have too fertile a soil but are either near the bigger urban markets or near the ports. For this, it has to be ensured that basic utilities-roads, electricity is present & law & order are maintained. In a Case Study of Village Neriga, Karnataka, India, Intel executives found that the key challenges faced by the villagers were lack of healthcare & lack of awareness about education, limited availability of electricity & safe drinking water though basic cell phone connections were available in each home. The company based upon such study invited young entrepreneurs to apply innovative technology-aided solutions for education, healthcare & other needs of the community."},
        {"type": "paragraph", "text": "Similarly, in Thamna village in Anand district of central Gujarat, farmer Ramn Parmar is perhaps the first farmer in the country to sell power harvested from his own farm & in June 2015, he got first cheque of Rs. 7500/- for the 1500 units of surplus power that was produced in his farm and was fed to the electricity grid during the last four months. The payment was made by International Water Management Institute (IWMI), which with the help of MGVCL (Madhya Gujarat Vij Company Ltd) — a state electricity discom — has set up this demonstration project in the village, as a viable business model for farmers who wish to harvest solar energy and add to their agricultural incomes (http://indianexpress.com)."}
      ],
      "tables": []
    },
    {
      "page_num": 11,
      "text_blocks": [
        {"type": "paragraph", "text": "Similarly, since 2007, Kabbigere village in Karnataka has been generating power and selling it to the grid through biomass. The gram panchayat sells the biomass generated power to Bengaluru Electricity Supply Company. This project is a joint initiative between UNDP- BERI along with the GEF, ICEF and Government of Karnataka’s Department of Rural Development and Panchayati Raj. Studies reveal that the village generated about 400,000 kWh of electricity in 2007. This equals the annual consumption of 6,000 rural households and has helped ensure more reliable electricity supply in the area. The above examples demonstrate how a systematic & scientific approach towards study & solutions for problems faced by the rural population can be effective."},
        {"type": "paragraph", "text": "It is not only the social-political & economic studies that can be undertaken by the students, researchers as well as administrators, in medical sciences also, it is important to carry out field studies to find out the ways & means to tackle a disease which may be specific to geographical locations."},
        {"type": "heading", "text": "4. Types of village studies"},
        {"type": "paragraph", "text": "It is now clear that to understand the problems & challenges faced by the large percentage of population of the country, village studies are need of the hour be it in socio-political or economic fields. The question arises as to what kind of studies should be carried out- macro level (small number of samples representing large picture) or micro level (larger samples covering maximum number of permutations amongst geo-political differences). The answer depends upon the type of problem that one is trying to solve. For example, the public delivery system (PDS) is more or less common across the country & the problem of leakages at various levels will also be the same. Hence, if smaller sample data but across the states is taken up, it should throw common thread of problems & likely solutions. However, if a social or political issue is taken up, it may need larger sample sizes spread across larger geographical space."},
        {"type": "paragraph", "text": "The decades of 1950 & 1960s were the times when sociologists & social anthropologists carried out extensive research in villages of India. Jodhka (2012) wrote about village studies. The companies also undertake studies in villages to assess the markets as well as part of their social corporate responsibilities. The motive of the former studies is to find ways & means to enhance profits of the company or the business while purpose of the latter studies is to carry out welfare measures for the community. It may be possible that certain welfare measures undertaken by a company will lead to increase in profit (though indirectly) in the form of enhanced goodwill. Integration of profits with enabling economic development in a cooperative form is found best in the white revolution in Gujarat, Maharashtra, Haryana & other such states where, for example, the Amul brand of dairy products has been very successful market leader & has been standing tall even amongst the competition from the multinational & private companies."}
      ],
      "tables": []
    },
    {
      "page_num": 12,
      "text_blocks": [
        {"type": "heading", "text": "5. Conclusions:"},
        {"type": "paragraph", "text": "According to Srinivas (1975): [The] social sciences are drawing too heavily on a small range of human experience, viz. the western–industrial, and equating it with the global. (Built into that equation is an ethno-centric assumption on the part of many westerners that all societies are travelling towards the ultimate goal of a western–industrial type of society.) Indian social scientists have a responsibility to resist such an equation, firstly, in order to better understand their society, and secondly, to contribute to the greater universalisation of their disciplines."},
        {"type": "paragraph", "text": "It has been established in the preceding paras, that village studies are important not only for academicians but for policy makers, administrators, corporate and scientists equally. Such studies undertaken with proper methodology & with defined objectives bring out the reasons or factors affecting an issue but also the possible solutions."},
        {"type": "heading", "text": "Summary:"},
        {"type": "paragraph", "text": "In one of his famous quotes, the most famous leader of 20th century India, Mahatma Gandhi said “India is not Calcutta and Bombay. India lives in her seven hundred thousand villages”. The studies of social structures start with a group of individuals & in such scenario, the small group of individuals residing in a hamlet or a small village constitute first basis of studies of bigger groups e.g. towns & semi-urban areas. In the villages of India, the residential quarters are often built based upon a strong caste system. The ties of caste & community in a village often cut across the economic classifications of a population. To understand the social interactions amongst various communities separated by physical spaces, the field studies are required so that implications of the same upon semi-urban areas can be deduced. In principle, the reservation of various sections of society (women, scheduled caste/scheduled tribe etc) is in place for formation of the Panchayats to encourage the participation of various social groups in political and economic development of villages. Due to varying geological & spatial factors, agricultural products & crops (both per year as well as in production per hectare) differ from one place to another. It is now clear that to understand the problems & challenges faced by the large percentage of population of the country, village studies are need of the hour be it in socio-political or economic fields. The question arises as to what kind of studies should be carried out- macro level (small number of samples representing large picture) or micro level (larger samples covering maximum number of permutations amongst geo-political differences). The answer depends upon the type of problem that one is trying to solve."}
      ],
      "tables": []
    }
  ]
}

out_dir = Path('scratch/test_gemini_out')
out_dir.mkdir(parents=True, exist_ok=True)
out_path = out_dir / '145793840413ET_gemini.json'

with open(out_path, 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print('Successfully generated 145793840413ET_gemini.json using simulated IDE build-in model.')
