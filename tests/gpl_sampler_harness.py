"""Execute the emitted sampler's small GPL subset for lifecycle regression tests.

This is not a Majesty VM or a save-format/scheduler emulator. It checks the
actual emitted branches, loops and record offsets; the stock compiler separately
checks GPL syntax. Native timing and save/load still need an in-game check.
"""
import re

from majesty_cam.gpl import parse_gpl

_TOKENS = re.compile(r'"(?:\\.|[^"\\])*"|//[^\r\n]*|/\*[\s\S]*?\*/|'
                     r"'s\b|[A-Za-z_][A-Za-z0-9_]*|\d+|==|!=|<=|>=|&&|\|\||<<|\+=|[^\s]")


class _Return(Exception):
    def __init__(self, value):
        self.value = value


class _Parser:
    def __init__(self, text):
        self.tokens = [s if s.startswith('"') else s.lower() for s in _TOKENS.findall(text)
                       if not s.startswith(("//", "/*"))]
        self.pos = 0

    def take(self, expected=None):
        token = self.tokens[self.pos]
        self.pos += 1
        if expected is not None:
            assert token == expected, (token, expected)
        return token

    def until(self, end):
        start = self.pos
        depth = 0
        while self.pos < len(self.tokens):
            token = self.tokens[self.pos]
            if token == end and depth == 0:
                value = self.tokens[start:self.pos]
                self.pos += 1
                return value
            depth += (token == "(") - (token == ")")
            self.pos += 1
        raise AssertionError(f"missing {end}")

    def statement(self):
        token = self.take()
        if token == "begin":
            result = []
            while self.tokens[self.pos] != "end":
                result.append(self.statement())
            self.take("end")
            return ("block", result)
        if token in ("if", "while"):
            self.take("(")
            condition = self.until(")")
            if token == "while":
                self.take("do")
            body = self.statement()
            alternate = None
            if token == "if" and self.pos < len(self.tokens) and self.tokens[self.pos] == "else":
                self.take()
                alternate = self.statement()
            return (token, condition, body, alternate)
        if token == "return":
            return (token, self.until(";"))
        self.pos -= 1
        return ("simple", self.until(";"))


class Agent:
    def __init__(self):
        self.fields = {}
        self.alive = True

    def __getitem__(self, key):
        return self.fields[key]

    def __setitem__(self, key, value):
        self.fields[key] = value


class SamplerHarness:
    def __init__(self, source):
        self.root = Agent()
        self.scheduled = False
        self.stops = 0
        self.calls = {}
        self.instructions = 0
        self.functions = {}
        for item in parse_gpl(source).items:
            parser = _Parser(item.text)
            parser.take("function")
            name = parser.take()
            parser.take("(")
            args = parser.until(")")
            params = [args[i + 1] for i in range(0, len(args), 3)]
            while parser.take() != "declare":
                pass
            defaults = {}
            while parser.tokens[parser.pos] != "begin":
                kind = parser.take()
                for local in parser.until(";"):
                    if local != ",":
                        defaults[local] = {"list": list, "integer": int, "boolean": bool,
                                          "agent": lambda: None, "string": str}[kind]
            self.functions[name] = (params, defaults, parser.statement())
        self.calls.update({name: self._bind(name) for name in self.functions})
        self.calls.update({
            # $NullAgent is a function value; only $NullAgent() returns an agent.
            # Treating the bare native symbol as None masks GPL call-shape bugs.
            "nullagent": lambda: None,
            "retrieveagent": lambda name: self.root,
            "hasattribute": lambda name, agent: name in agent.fields,
            "addattribute": self.add_attribute,
            "isvalidgamepiece": lambda agent: isinstance(agent, Agent),
            "isdead": lambda agent: not agent.alive,
            "listsize": len,
            "listmember": lambda values, index: values[index - 1],
            "newthread": self.start_thread,
            "killthread": self.stop_thread,
        })

    def _bind(self, name):
        return lambda *args: self.call(name, *args)

    def add_attribute(self, agent, name, kind, value=None):
        if name in agent.fields:
            return False
        agent[name] = [] if kind == "list" else value
        return True

    def start_thread(self, callback, interval):
        assert callable(callback), "NewThread requires a function value, not its result"
        assert not self.scheduled
        assert interval == 1000
        self.scheduled = True

    def stop_thread(self, callback):
        # No nested terminal callback may kill its caller's pending dispatch.
        assert not self.root["MM_ActivityTicking_v1"]
        self.scheduled = False
        self.stops += 1

    def expression(self, tokens):
        output = []
        index = 0
        while index < len(tokens):
            token = tokens[index]
            if token == "$":
                index += 1
                output.append("F[" + repr(tokens[index]) + "]")
            elif token == "'s":
                index += 1
                output.append("[" + tokens[index] + "]")
            else:
                output.append({"&&": "and", "||": "or", "true": "True", "false": "False"}.get(token, token))
            index += 1
        return " ".join(output)

    def value(self, tokens, env):
        return eval(self.expression(tokens), {"__builtins__": {}, "F": self.calls}, env)

    def run(self, node, env):
        self.instructions += 1
        assert self.instructions < 1000000, "unbounded sampler loop"
        kind = node[0]
        if kind == "block":
            for child in node[1]:
                self.run(child, env)
        elif kind == "if":
            child = node[2] if self.value(node[1], env) else node[3]
            if child is not None:
                self.run(child, env)
        elif kind == "while":
            while self.value(node[1], env):
                self.run(node[2], env)
        elif kind == "return":
            raise _Return(self.value(node[1], env) if node[1] else None)
        elif kind == "simple":
            tokens = node[1]
            if "<<" in tokens:
                pos = tokens.index("<<")
                self.value(tokens[:pos], env).append(self.value(tokens[pos + 1:], env))
            elif "=" in tokens or "+=" in tokens:
                exec(self.expression(tokens), {"__builtins__": {}, "F": self.calls}, env)
            else:
                self.value(tokens, env)
        else:
            raise AssertionError(kind)

    def call(self, name, *args):
        params, defaults, body = self.functions[name.lower()]
        assert len(params) == len(args)
        env = {key: factory() for key, factory in defaults.items()}
        env.update(zip(params, args))
        try:
            self.run(body, env)
        except _Return as result:
            return result.value

    def tick(self):
        if self.scheduled:
            self.call("MM_AD_Tick")
