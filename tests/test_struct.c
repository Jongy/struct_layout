struct other_struct {
    int some_field;
};

struct test_struct {
    int first_field;
    char second_field;
    unsigned long *third_field;
    float last_field;

    // arrays are broken
    // char array[1];

    // pointers to pointers are broken
    // void **p;

    // other structs are a bit broken
    // struct other_struct z;
};
