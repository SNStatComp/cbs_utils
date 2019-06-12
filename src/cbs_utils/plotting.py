import collections
CBS_COLORS_RBG = {
    "corporateblauw": (39, 29, 108),
    "corporatelichtblauw": (0, 161, 205),
    "lichtgrijs": (236, 236, 236),
    "geel": (255, 204, 0),
    "geelvergrijsd": (255, 182, 0),
    "oranje": (243, 146, 0),
    "oranjevergrijsd": (206, 124, 0),
    "rood": (233, 76, 10),
    "roodvergrijsd": (178, 61, 2),
    "roze": (175, 14, 128),
    "rozevergrijsd": (130, 4, 94),
    "donkerblauw": (0, 88, 184),
    "donkerblauwvergrijsd": (22, 58, 114),
    "lichtblauwvergrijsd": (5, 129, 162),
    "grasgroen": (83, 163, 29),
    "grasgroenvergrijsd": (72, 130, 37),
    "appelgroen": (175, 203, 5),
    "appelgroenvergrijsd": (137, 157, 12),
}

CBS_COLORS = {"cbs:" + name: (value[0]/255, value[1]/255, value[2]/255) 
              for name, value in CBS_COLORS_RBG.items()}

