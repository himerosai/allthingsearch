# All Things Search

We have ElasticSearch for indexing text documents which is great if you are a librarian, but you are a videogame studio and you need to search your 3d objects, meshes, audio, texture, images and concept art.

What tools do you have? I am building just that!

# Overall design

Design pre-GPT:

![diagram](https://github.com/himerosai/allthingsearch/assets/153864679/b2c8049d-661b-41bb-a50d-c00bfbc63ad1)

Design post-GPT:

![image](https://github.com/himerosai/allthingsearch/assets/153864679/f89c445d-68e4-45c3-bb2d-ce7634f0b682)

I will combine both approaches.
# Dependecies (so far):

Frontend: Gradio

Backend Text Search: ElasticSearch

Database storage: MiniIO

Agent: Langchain + RAG

Workaround, Poetry is amazingly slow!

```
poetry export -f requirements.txt > requirements.txt
python -m pip install -r requirements.txt
poetry install
```

Algorithms:
* 3D-VisTA: https://github.com/3d-vista/3D-VisTA
* Cap3D: https://github.com/crockwell/Cap3D/tree/main

# What's the math?

Check the Wiki where I referenced all the interesting papers published in this subject.

# Inspiration

Heaviy inspired by:

* https://gfx.cs.princeton.edu/proj/shape/
* https://modelnet.cs.princeton.edu/

# Updates

Follow me on [twitter](https://x.com/HimerosAI)

