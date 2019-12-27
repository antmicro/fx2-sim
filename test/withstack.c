
struct mystruct {
  int x;
  int y;
};

int main()
{
  struct mystruct value = { .x = 1, .y = 2 };

  while (1) {
    value.x += value.y;
  }
}
