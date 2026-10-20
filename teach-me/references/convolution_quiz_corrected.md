# $1^{st}$ lesson quiz

This quiz explores the convolution of images

## ❓ Convolution

Given two images, $I_1$ and $I_2$, whose pixels values follow this notation :

$$
I(x, y) = c
$$

where $c$ is a floating number between 0.0 and 1.0, answer the following questions

### What is the convolution of $I_1$ and $I_2$ ?

*Multiple responses are possible.*

- [x] **A.** $(I_1 * I_2)(X, Y) = \int_{-\infty}^{+\infty}\int_{-\infty}^{+\infty} I_1(x, y)\, I_2(X - x, Y - y)\, dx\, dy$
- [ ] **B.** $(I_1 * I_2)(X, Y) = \int_{-\infty}^{+\infty}\int_{-\infty}^{+\infty} I_1(X - x, Y - y)\, I_2(x, y)\, dx\, dy$
- [ ] **C.** $(I_1 * I_2)(X, Y) = \int_{-\infty}^{+\infty}\int_{-\infty}^{+\infty} I_1(x, y)\, I_2(x - X, y - Y)\, dx\, dy$
- [ ] **D.** $(I_1 * I_2)(X, Y) = \int_{-\infty}^{+\infty}\int_{-\infty}^{+\infty} I_1(x, y)\, I_2(x + X, y + Y)\, dx\, dy$

> [!Warning] Incomplete answer
> Answer B was also true, which can be demonstrated using the variable switch $x' = X - x$, $y' = Y - y$ : the convolution is commutative.
> As long as you are covering the whole images (⚠️ pay attention to the limits of the integrals being $-\infty$ and $+\infty$ !) and one of the two images is flipped ($X - x$), it can be expressed in different ways !
> 
> C and D don't flip $I_2$ : they are **cross-correlations**, which are equal to the convolution only when $I_2$ is symmetric. 💡 Fun fact : the "convolution" layers of PyTorch and TensorFlow actually compute a cross-correlation. Since the kernel is learnt, flipping it or not doesn't change anything !

### Is there a neutral element in the convolution ?

We work with discrete images, zero padding, and we keep the size of the input image (`same` mode). Is there a kernel $K$ such that $\text{Image} * K = \text{Image}$ for every image ?

*Multiple responses are possible.*

- [ ] **A.** Yes : a kernel full of zeros, except a one in its center, as long as its dimensions are odd
- [x] **B.** No, there isn't
- [ ] **C.** Yes, and there is one for every odd kernel size ($1 \times 1$, $3 \times 3$, $5 \times 5$, ...)
- [ ] **D.** Only if both dimensions of the image are odd

> [!Failure] Incorrect answer
> Answers A and C are correct.
> If you use a kernel with only zeros, except its center with a one like for instance :
> $$
> K = \begin{pmatrix}
> 0 & 0 & 0\\
> 0 & 1 & 0\\
> 0 & 0 & 0\\
> \end{pmatrix}
> $$
> It is a neutral element that verifies :
> $$
> \forall \text{Image}, \quad
> \text{Image} * K = \text{Image}
> $$
> ⚠️ Pay attention that the kernel must have odd dimensions for this to work : an even kernel has no center, so its one is off-center and the result is shifted by one pixel ! The dimensions of the image don't matter.
> 💡 In the continuous world, the neutral element is the Dirac delta $\delta$.

### What is the property associated with Fourier transform and convolution ?

*Multiple responses are possible.*

- [x] **A.** The Fourier Transform of the convolution of two functions is the product of their 2 Fourier Transforms
- [ ] **B.** The convolution of the Fourier Transforms of two functions is the product of their 2 Fourier Transforms
- [x] **C.** The convolution of two functions is the inverse Fourier Transform of the product of their Fourier Transforms
- [ ] **D.** The Fourier Transform of the convolution of two functions is the convolution of their Fourier Transforms

> [!Success] Correct answer
> 🎉 You have found every good answer !
